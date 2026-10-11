"""IoT Core custom authorizer: token sources, principal and policy, rejections."""

import base64
import hashlib
import importlib.util
import json
from types import SimpleNamespace

import pytest

from tests.conftest import REPO

KEY = "s3cretKeyForGroupOne"
ARN = "arn:aws:lambda:eu-west-1:123456789012:function:bus-iot-authorizer"
CONTEXT = SimpleNamespace(invoked_function_arn=ARN)


@pytest.fixture
def auth(monkeypatch):
    monkeypatch.setenv("KEY_HASHES", json.dumps({hashlib.sha256(KEY.encode()).hexdigest(): "group-1 (Los Buses)"}))
    handler = REPO / "src" / "lambda" / "iot-authorizer" / "handler.py"
    spec = importlib.util.spec_from_file_location("iot_authorizer", handler)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mqtt_event(password: str | None) -> dict:
    mqtt = {"username": "?x-amz-customauthorizer-name=bus-groups", "clientId": "student-1"}
    if password is not None:
        mqtt["password"] = base64.b64encode(password.encode()).decode()
    return {"signatureVerified": False, "protocols": ["tls", "mqtt"], "protocolData": {"mqtt": mqtt}}


def http_event(query: str = "", headers: dict | None = None) -> dict:
    return {"signatureVerified": False, "protocols": ["tls", "http"],
            "protocolData": {"http": {"headers": headers or {}, "queryString": query}}}


def assert_allowed(response):
    assert response["isAuthenticated"] is True
    assert response["principalId"] == "group1LosBuses"
    assert response["disconnectAfterInSeconds"] == 86400 and response["refreshAfterInSeconds"] == 3600
    (doc,) = response["policyDocuments"]
    allowed = {s["Action"]: s["Resource"] for s in doc["Statement"] if s["Effect"] == "Allow"}
    assert allowed == {
        "iot:Connect": "arn:aws:iot:eu-west-1:123456789012:client/*",
        "iot:Subscribe": "arn:aws:iot:eu-west-1:123456789012:topicfilter/madrid/*",
        "iot:Receive": "arn:aws:iot:eu-west-1:123456789012:topic/madrid/*",
    }
    assert len(json.dumps(doc)) <= 2048


def test_mqtt_password(auth):
    assert_allowed(auth.handler(mqtt_event(KEY), CONTEXT))


def test_websocket_query_string(auth):
    assert_allowed(auth.handler(http_event(f"?x-amz-customauthorizer-name=bus-groups&token={KEY}"), CONTEXT))
    assert_allowed(auth.handler(http_event(f"x-amz-customauthorizer-name=bus-groups&token={KEY}"), CONTEXT))


def test_header(auth):
    assert_allowed(auth.handler(http_event(headers={"X-Api-Key": KEY}), CONTEXT))


@pytest.mark.parametrize("event", [
    mqtt_event("wrong"),
    mqtt_event(None),
    http_event("x-amz-customauthorizer-name=bus-groups&token=wrong"),
    http_event(headers={"x-api-key": ""}),
    {"protocolData": {"mqtt": {"password": "%%%not-base64"}}},
    {},
])
def test_rejected(auth, event):
    assert auth.handler(event, CONTEXT) == {"isAuthenticated": False}
