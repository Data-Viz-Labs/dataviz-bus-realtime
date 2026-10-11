"""AWS IoT Core custom authorizer (signing disabled): one access key per hackathon group.

The key is read from, in order: the MQTT CONNECT password, the ``token`` query string
parameter of a WebSocket URL, or the ``x-api-key`` header. Only SHA-256 hashes of the keys
are known here (``KEY_HASHES``: {"<sha256 hex>": "<group>"}). Groups may only subscribe to
and receive ``madrid/*``; publishing is the simulator's job.
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
from urllib.parse import parse_qs

KEY_HASHES: dict[str, str] = json.loads(os.environ.get("KEY_HASHES", "{}"))
DENY = {"isAuthenticated": False}


def _tokens(event: dict) -> list[str]:
    data = event.get("protocolData") or {}
    out = []
    if password := (data.get("mqtt") or {}).get("password"):
        try:
            out.append(base64.b64decode(password).decode())
        except (binascii.Error, UnicodeDecodeError):
            pass
    http = data.get("http") or {}
    if query := http.get("queryString"):
        out += parse_qs(query.lstrip("?")).get("token", [])
    headers = {k.lower(): v for k, v in (http.get("headers") or {}).items()}
    if key := headers.get("x-api-key"):
        out.append(key)
    return out


def group_for(token: str) -> str | None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    for known, group in KEY_HASHES.items():
        if hmac.compare_digest(digest, known):
            return group
    return None


def policy(region: str, account: str) -> dict:
    arn = f"arn:aws:iot:{region}:{account}"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": "iot:Connect", "Resource": f"{arn}:client/*"},
            {"Effect": "Allow", "Action": "iot:Subscribe", "Resource": f"{arn}:topicfilter/madrid/*"},
            {"Effect": "Allow", "Action": "iot:Receive", "Resource": f"{arn}:topic/madrid/*"},
        ],
    }


def handler(event, context):
    group = next((g for t in _tokens(event) if t and (g := group_for(t))), None)
    if group is None:
        return DENY
    # arn:aws:lambda:<region>:<account>:function:<name>
    _, _, _, region, account, *_ = context.invoked_function_arn.split(":")
    return {
        "isAuthenticated": True,
        "principalId": re.sub(r"[^A-Za-z0-9]", "", group)[:128] or "group",
        "disconnectAfterInSeconds": 86400,
        "refreshAfterInSeconds": 3600,
        "policyDocuments": [policy(region, account)],
    }
