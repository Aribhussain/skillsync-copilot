import importlib.util
import json

from app.core.config import REPO_ROOT

HINT = "stale fixture - run: python scripts/export_parity_fixture.py"


def test_parity_fixture_and_seed_pack_are_up_to_date():
    """The TS mapper-lite / evidence-plan parity fixtures must be regenerated whenever the
    corpus, lexicon, tokenizer, mapper or evidence rules change."""
    spec = importlib.util.spec_from_file_location("exp", REPO_ROOT / "scripts" / "export_parity_fixture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pack, parity = mod.build()
    fixture = json.loads((mod.OUT / "parity.json").read_text(encoding="utf-8"))
    seed = json.loads(mod.SEED_PACK.read_text(encoding="utf-8"))
    assert seed["pack_version"] == pack["pack_version"], HINT
    assert fixture["pack_version"] == parity["pack_version"], HINT
    assert fixture["cases"] == parity["cases"], HINT
    assert fixture["plans"] == parity["plans"], HINT
