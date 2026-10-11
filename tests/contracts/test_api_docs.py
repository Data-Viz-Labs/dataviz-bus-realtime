import importlib.util

import yaml

from tests.conftest import REPO
from tests.lambdas.test_api_handler import handler, mcp

DOCS = REPO / "docs" / "api"
SITE_PATHS = {"/live/snapshot.json", "/live/config.json", "/network.json"}  # served by CloudFront, no key


def openapi() -> dict:
    return yaml.safe_load((DOCS / "openapi.yaml").read_text())


def test_every_route_is_documented_and_every_documented_route_exists():
    spec = openapi()
    documented = {(method.upper(), path) for path, item in spec["paths"].items() if path not in SITE_PATHS
                  for method in item if method in ("get", "post", "put", "delete", "patch")}
    routes = {(method, path) for method, path, _, _ in handler.ROUTES}
    assert documented == routes


def test_public_routes_need_no_key_and_site_files_use_the_site_server():
    spec = openapi()
    public = {path for _, path, _, private in handler.ROUTES if not private}
    for path in public:
        assert spec["paths"][path]["get"]["security"] == []
    for path in SITE_PATHS:
        op = spec["paths"][path]["get"]
        assert op["security"] == [] and "site_url" in op["servers"][0]["url"]
    assert {"apiKey", "bearer"} <= set(spec["components"]["securitySchemes"])


def test_every_mcp_tool_is_documented_and_the_reference_is_up_to_date():
    text = (DOCS / "mcp.md").read_text()
    for tool in mcp.TOOLS:
        assert f"### `{tool.name}`" in text
    spec = importlib.util.spec_from_file_location("export_mcp_docs", REPO / "bin" / "export_mcp_docs.py")
    export = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export)
    assert set(export.EXAMPLES) == {t.name for t in mcp.TOOLS}
    assert export.update(text, mcp.TOOLS) == text, "run: python bin/export_mcp_docs.py"
