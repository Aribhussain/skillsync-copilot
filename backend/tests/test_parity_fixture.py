import importlib.util
import json

from app.core.config import REPO_ROOT


def test_parity_fixture_is_up_to_date():
    """The TS mapper-lite parity fixture must be regenerated when corpus/lexicon/tokenizer change."""
    spec = importlib.util.spec_from_file_location("exp", REPO_ROOT / "scripts" / "export_parity_fixture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pack, _ = mod.build()
    fixture = json.loads((mod.OUT / "parity.json").read_text(encoding="utf-8"))
    assert fixture["pack_version"] == pack["pack_version"], "run: python scripts/export_parity_fixture.py"
