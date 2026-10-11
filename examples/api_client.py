"""Minimal client of the Madrid bus API, standard library only.

    export API_URL=$(terraform -chdir=iac/stack output -raw api_url)
    export API_KEY=<your group key>
    python examples/api_client.py [line_id]

Prints the live state of a line, last week's hourly history of that line (as a pandas DataFrame
when pandas is installed, as CSV otherwise) and the result of a SQL query.
"""

import csv
from datetime import date, timedelta
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_URL = os.environ.get("API_URL", "").rstrip("/")
API_KEY = os.environ.get("API_KEY", "")


def api(path: str, params: dict | None = None, body: dict | None = None) -> dict:
    """GET (or POST with a JSON body) and return the decoded JSON; API errors are raised as SystemExit."""
    url = f"{API_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"x-api-key": API_KEY, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=70) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        error = json.loads(e.read() or b"{}").get("error", {})
        raise SystemExit(f"{e.code} {error.get('code')}: {error.get('message')}") from None


def print_table(result: dict) -> None:
    """Tabular results come as columns + rows."""
    try:
        import pandas as pd
    except ImportError:
        writer = csv.writer(sys.stdout)
        writer.writerow(result["columns"])
        writer.writerows(result["rows"])
        return
    print(pd.DataFrame(result["rows"], columns=result["columns"]).to_string(index=False))


def main(line_id: str = "27") -> None:
    if not API_URL or not API_KEY:
        raise SystemExit("set API_URL and API_KEY")

    live = api(f"/v1/live/lines/{line_id}")
    print(f"Line {line_id} at {live['time']}: {live['buses_in_service']} buses, {live['passengers']} on board, "
          f"{live['waiting']} waiting")
    busiest = max(live["stops"]["outbound"] + live["stops"]["inbound"], key=lambda s: s["waiting"])
    print(f"Most people waiting: {busiest['waiting']} at {busiest['name']} ({busiest['id']})\n")

    end = date.today() - timedelta(days=1)
    hourly = api(f"/v1/history/lines/{line_id}/hourly",
                 {"from": (end - timedelta(days=6)).isoformat(), "to": end.isoformat(), "direction": 0})
    print(f"Hourly history, outbound, {hourly['from']}..{hourly['to']} ({hourly['row_count']} rows):")
    print_table(hourly)

    month = end.strftime("%Y-%m")
    sql = api("/v1/sql", body={"query": f"""
        SELECT hour, round(avg(avg_load), 3) AS avg_load, sum(boardings) AS boardings
        FROM line_hourly
        WHERE month = '{month}' AND line_id = '{line_id}'
        GROUP BY hour ORDER BY hour"""})
    print(f"\nLoad by hour of day in {month} (scanned {sql['stats']['data_scanned_bytes']} bytes):")
    print_table(sql)


if __name__ == "__main__":
    main(*sys.argv[1:2])
