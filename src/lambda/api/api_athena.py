"""Athena helpers: run a query and read typed rows, and the guard for user-written SQL.

No third-party dependencies besides the boto3 client passed in, so the module is easy to test
with botocore's Stubber.
"""

import re
import time

MAX_SQL_ROWS = 10_000
MAX_SQL_CHARS = 20_000
TIMEOUT_S = 50.0

INTS = {"tinyint", "smallint", "integer", "int", "bigint"}
FLOATS = {"double", "float", "real", "decimal"}
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CALL|EXECUTE|PREPARE|DEALLOCATE"
    r"|UNLOAD|MSCK|REPAIR|VACUUM|OPTIMIZE|SET|RESET|USE|SHOW|DESCRIBE|EXPLAIN)\b",
    re.IGNORECASE,
)


class SqlError(ValueError):
    """The query is not a single read-only SELECT."""


class QueryFailed(Exception):
    """Athena rejected or failed the query; the message is Athena's reason."""


class QueryTimeout(Exception):
    """The query did not finish in time and was cancelled."""


# --- SQL guard --------------------------------------------------------------------------------

def _scan(sql: str) -> tuple[str, str]:
    """Return (sql without comments, skeleton with string literals and quoted identifiers blanked)."""
    out, skel, i, n = [], [], 0, len(sql)
    while i < n:
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
            out.append(" ")
            skel.append(" ")
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            if j < 0:
                raise SqlError("unterminated /* comment")
            i = j + 2
            out.append(" ")
            skel.append(" ")
        elif sql[i] in "'\"":
            quote, j = sql[i], i + 1
            while True:
                j = sql.find(quote, j)
                if j < 0:
                    raise SqlError("unterminated string literal or quoted identifier")
                if sql.startswith(quote * 2, j):
                    j += 2
                    continue
                break
            out.append(sql[i:j + 1])
            skel.append(quote * 2)
            i = j + 1
        else:
            out.append(sql[i])
            skel.append(sql[i])
            i += 1
    return "".join(out), "".join(skel)


def guard_sql(sql: str, max_rows: int = MAX_SQL_ROWS) -> str:
    """Validate a user query and return it with comments removed and a LIMIT of at most ``max_rows``.

    Accepts one SELECT or WITH statement (trailing semicolons are dropped). Rejects other
    statements, DDL/DML keywords outside string literals and FETCH FIRST.
    """
    if not sql or not sql.strip():
        raise SqlError("query is empty")
    if len(sql) > MAX_SQL_CHARS:
        raise SqlError(f"query is longer than {MAX_SQL_CHARS} characters")
    clean, skel = _scan(sql)
    clean, skel = clean.strip().rstrip(";").rstrip(), skel.strip().rstrip(";").rstrip()
    if ";" in skel:
        raise SqlError("only one statement is allowed (remove ';')")
    if not re.match(r"\(*\s*(SELECT|WITH)\b", skel, re.IGNORECASE):
        raise SqlError("only SELECT or WITH queries are allowed")
    if m := FORBIDDEN.search(skel):
        raise SqlError(f"keyword {m.group(1).upper()} is not allowed: the dataset is read-only")
    if re.search(r"\bFETCH\b", skel, re.IGNORECASE):
        raise SqlError("use LIMIT instead of FETCH FIRST")
    m = re.search(r"\bLIMIT\s+(\d+|ALL)\s*$", skel, re.IGNORECASE)
    if m:
        n = max_rows if m.group(1).upper() == "ALL" else min(int(m.group(1)), max_rows)
        return f"{clean[:len(clean) - len(m.group(0))]}LIMIT {n}"
    return f"{clean}\nLIMIT {max_rows}"


def quote(value: str) -> str:
    """A SQL string literal, for Athena ExecutionParameters."""
    return "'" + value.replace("'", "''") + "'"


# --- Execution --------------------------------------------------------------------------------

def convert(value: str | None, athena_type: str):
    """Athena returns every value as a string: give it back its JSON type."""
    if value is None:
        return None
    t = athena_type.lower()
    if t in INTS:
        return int(value)
    if t in FLOATS:
        return float(value)
    if t == "boolean":
        return value == "true"
    return value  # varchar, date ('2026-10-11'), timestamp ('2026-10-11 08:00:00.000'), ...


def run(client, sql: str, *, database: str, workgroup: str, params: list[str] | None = None,
        max_rows: int = MAX_SQL_ROWS, timeout_s: float | None = None) -> dict:
    """Run ``sql`` and return {columns, types, rows, row_count, truncated, query_id, stats}.

    Polls with a growing delay (0.25 s to 2 s); after ``timeout_s`` (default ``TIMEOUT_S``) the
    query is stopped and ``QueryTimeout`` raised.
    """
    kwargs = {"QueryString": sql, "WorkGroup": workgroup, "QueryExecutionContext": {"Database": database}}
    if params:
        kwargs["ExecutionParameters"] = params
    qid = client.start_query_execution(**kwargs)["QueryExecutionId"]

    deadline, delay = time.monotonic() + (TIMEOUT_S if timeout_s is None else timeout_s), 0.25
    while True:
        ex = client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = ex["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            raise QueryFailed(ex["Status"].get("StateChangeReason", state))
        if time.monotonic() + delay > deadline:
            client.stop_query_execution(QueryExecutionId=qid)
            raise QueryTimeout(qid)
        time.sleep(delay)
        delay = min(delay * 1.6, 2.0)

    columns: list[str] = []
    types: list[str] = []
    rows: list[list] = []
    truncated = False
    pages = client.get_paginator("get_query_results").paginate(
        QueryExecutionId=qid, PaginationConfig={"PageSize": 1000})
    for page in pages:
        data = page["ResultSet"]["Rows"]
        if not columns:
            info = page["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
            columns, types = [c["Name"] for c in info], [c["Type"] for c in info]
            data = data[1:]  # the first row of a SELECT result holds the column names
        for r in data:
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append([convert(d.get("VarCharValue"), t) for d, t in zip(r["Data"], types, strict=False)])
        if truncated:
            break
    stats = ex.get("Statistics", {})
    return {
        "columns": columns, "types": types, "rows": rows, "row_count": len(rows), "truncated": truncated,
        "query_id": qid,
        "stats": {"data_scanned_bytes": stats.get("DataScannedInBytes"),
                  "execution_ms": stats.get("TotalExecutionTimeInMillis")},
    }
