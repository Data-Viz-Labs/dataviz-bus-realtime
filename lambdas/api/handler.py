"""HTTP API and MCP server of the Madrid bus simulator (Lambda function URL, payload v2).

Every route but ``/v1/health`` needs a group key in ``x-api-key`` or ``Authorization: Bearer``.
Only SHA-256 hashes of the keys are known here (``KEY_HASHES`` = {"<sha256 hex>": "<group>"}).

Environment: DATA_BUCKET, SITE_BUCKET, GLUE_DATABASE, ATHENA_WORKGROUP, KEY_HASHES.
"""

import base64
from collections.abc import Callable
import hashlib
import hmac
import json
import logging
import os
import re
import time
from urllib.parse import unquote

import api_data as service
from api_data import ApiError
import api_mcp as mcp_server

log = logging.getLogger()
log.setLevel(logging.INFO)

MAX_RESPONSE_BYTES = 5_500_000  # function URL responses are limited to 6 MB

# (method, path template, function, needs a key). /mcp is handled apart.
ROUTES: list[tuple[str, str, Callable[[dict], dict] | None, bool]] = [
    ("GET", "/v1/health", service.health, False),
    ("GET", "/v1/lines", service.list_lines, True),
    ("GET", "/v1/lines/{line_id}", service.get_line, True),
    ("GET", "/v1/stops", service.list_stops, True),
    ("GET", "/v1/stops/{stop_id}", service.get_stop, True),
    ("GET", "/v1/live/buses", service.live_buses, True),
    ("GET", "/v1/live/lines/{line_id}", service.live_line, True),
    ("GET", "/v1/live/stops/{stop_id}", service.live_stop, True),
    ("GET", "/v1/history/lines/{line_id}/hourly", service.line_hourly, True),
    ("GET", "/v1/history/stops/{stop_id}/hourly", service.stop_hourly, True),
    ("GET", "/v1/history/stop-calls", service.stop_calls, True),
    ("GET", "/v1/history/positions", service.positions, True),
    ("POST", "/v1/sql", service.run_sql, True),
    ("GET", "/v1/datasets", service.datasets, True),
    ("GET", "/v1/datasets/{table}/files", service.dataset_files, True),
    ("POST", "/mcp", None, True),
]
_PATTERNS = [(re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path) + "$"), method, path, fn, private)
             for method, path, fn, private in ROUTES]


def _key_hashes() -> dict[str, str]:
    return service.cached("key_hashes", 300, lambda: json.loads(os.environ.get("KEY_HASHES") or "{}"))


def authenticate(headers: dict) -> str | None:
    """The group owning the request's key, or None."""
    key = headers.get("x-api-key", "").strip()
    auth = headers.get("authorization", "")
    if not key and auth[:7].lower() == "bearer ":
        key = auth[7:].strip()
    if not key:
        return None
    digest = hashlib.sha256(key.encode()).hexdigest()
    group = None
    for known, name in _key_hashes().items():  # compare with every hash: constant time
        if hmac.compare_digest(known, digest):
            group = name
    return group


def _response(status: int, payload=None, headers: dict | None = None) -> dict:
    out = {"statusCode": status, "headers": {"cache-control": "no-store", **(headers or {})}}
    if payload is not None:
        out["headers"]["content-type"] = "application/json"
        out["body"] = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return out


def _error(status: int, code: str, message: str, headers: dict | None = None) -> dict:
    return _response(status, {"error": {"code": code, "message": message}}, headers)


def _body(event: dict) -> str:
    body = event.get("body") or ""
    return base64.b64decode(body).decode() if event.get("isBase64Encoded") else body


def _route(event: dict) -> tuple[dict, str, str | None]:
    """Handle the request: (response, label for the log, group)."""
    method = event["requestContext"]["http"]["method"]
    path = event.get("rawPath", "/").rstrip("/") or "/"
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if method == "OPTIONS":  # the function URL answers CORS preflights itself; this is a fallback
        return _response(204), "OPTIONS", None

    found = [(m, path_tpl, fn, private, match) for pattern, m, path_tpl, fn, private in _PATTERNS
             if (match := pattern.match(path))]
    if not found:
        return _error(404, "not_found", f"no route {path}: see /docs.html"), path, None
    allowed = [f for f in found if f[0] == method]
    if not allowed:
        allow = ", ".join(sorted({f[0] for f in found}))
        return _error(405, "method_not_allowed", f"{method} is not allowed on {path}", {"allow": allow}), path, None
    _, template, fn, private, match = allowed[0]
    label = f"{method} {template}"

    group = authenticate(headers) if private else None
    if private and group is None:
        return _error(401, "unauthorized", "missing or invalid key: send x-api-key or Authorization: Bearer"), \
            label, None

    if template == "/mcp":
        status, payload, rpc = mcp_server.handle(_body(event), headers)
        return _response(status, payload), f"{label} {rpc}", group

    params = dict(event.get("queryStringParameters") or {})
    params.update({k: unquote(v) for k, v in match.groupdict().items()})
    if method == "POST":
        try:
            body = json.loads(_body(event) or "{}")
        except ValueError:
            return _error(400, "bad_request", "body must be JSON"), label, group
        if not isinstance(body, dict):
            return _error(400, "bad_request", "body must be a JSON object"), label, group
        params.update({k: v for k, v in body.items() if isinstance(v, str)})
    try:
        result = fn(params)
    except ApiError as e:
        return _error(e.status, e.code, e.message), label, group
    response = _response(200, result)
    if len(response["body"].encode()) > MAX_RESPONSE_BYTES:
        response = _error(413, "too_large", "the response is over 6 MB: narrow the range, add filters or a LIMIT, "
                                            "or download Parquet files from /v1/datasets/{table}/files")
    return response, label, group


def lambda_handler(event: dict, context=None) -> dict:
    started = time.monotonic()
    try:
        response, label, group = _route(event)
    except Exception:
        log.exception("unhandled error")
        response, label, group = _error(500, "internal", "internal error"), "error", None
    log.info(json.dumps({"group": group, "route": label, "status": response["statusCode"],
                         "ms": round((time.monotonic() - started) * 1000)}))
    return response
