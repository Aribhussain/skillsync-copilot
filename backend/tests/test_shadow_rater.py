import pytest

from app.core.config import REPO_ROOT
from app.ml.shadow_rater import DEFECTS, MODEL_LABEL, load_rater
from app.ml.weld_features import FEATURE_NAMES, extract_from_bytes
from app.services.qp_store import iter_pcs, load_corpus

SAMPLES = REPO_ROOT / "frontend" / "public" / "samples"
WELDING = "QG-4.5-AU-01811-2024-V1-ASDC"


@pytest.fixture(scope="module")
def rater():
    return load_rater()


@pytest.fixture(scope="module")
def pcs():
    return {p["id"]: p for p in iter_pcs(load_corpus()[WELDING])}


def test_features_are_finite_and_complete():
    f = extract_from_bytes((SAMPLES / "weld_00_good.jpg").read_bytes())
    assert list(f) == FEATURE_NAMES
    assert all(v == v and abs(v) < 1e6 for v in f.values())  # no NaN / inf


@pytest.mark.parametrize(
    ("sample", "defect"),
    [
        ("weld_00_good.jpg", "good"),
        ("weld_04_porosity.jpg", "porosity"),
        ("weld_06_undercut.jpg", "undercut"),
        ("weld_08_spatter.jpg", "spatter"),
        ("weld_10_incomplete.jpg", "incomplete"),
    ],
)
def test_demo_model_reads_each_defect_class(rater, sample, defect):
    a = rater.analyse((SAMPLES / sample).read_bytes())
    assert a.defect == defect
    assert set(a.defect_probs) == set(DEFECTS)
    assert abs(sum(a.defect_probs.values()) - 1) < 1e-3
    assert a.explanation


def test_per_pc_suggestions_follow_the_signal(rater, pcs):
    porous = rater.analyse((SAMPLES / "weld_04_porosity.jpg").read_bytes())
    good = rater.analyse((SAMPLES / "weld_00_good.jpg").read_bytes())
    # porosity PC on a porous weld: low level, explanation mentions pores
    s = rater.suggest(pcs["ASC-N3125.PC1"], porous)
    assert s["level"] <= 2 and "pore" in s["explanation"]
    # spatter PC on a porous weld: that aspect is acceptable
    assert rater.suggest(pcs["ASC-N3125.PC3"], porous)["level"] == 2
    # any image PC on a good weld: top level
    assert rater.suggest(pcs["ASC-N3125.PC1"], good)["level"] == 3
    # observation / viva PCs never get an AI opinion
    assert rater.suggest(pcs["ASC-N3124.PC3"], good) is None
    assert rater.suggest(pcs["ASC-N9819.PC5"], good) is None
    # image PC with no photo yet
    assert rater.suggest(pcs["ASC-N3125.PC1"], None)["status"] == "awaiting_photo"


def test_model_is_labelled_as_a_synthetic_demo(rater, pcs):
    assert "synthetic" in MODEL_LABEL.lower() and "not for certification" in MODEL_LABEL.lower()
    good = rater.analyse((SAMPLES / "weld_00_good.jpg").read_bytes())
    assert rater.suggest(pcs["ASC-N3125.PC1"], good)["model_label"] == MODEL_LABEL
