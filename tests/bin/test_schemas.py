import importlib.util
import json

from tests.conftest import REPO

spec = importlib.util.spec_from_file_location("export_schemas", REPO / "bin" / "export_schemas.py")
export_schemas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_schemas)


def test_generated_schema_files_are_up_to_date():
    """Run `make schemas` after changing sim/history.py."""
    assert json.loads(export_schemas.TF_OUT.read_text()) == export_schemas.terraform_schema()
    assert export_schemas.DOC_OUT.read_text() == export_schemas.datasets_md()
