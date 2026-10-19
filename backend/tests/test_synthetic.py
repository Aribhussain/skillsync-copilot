import importlib.util
import random

from app.core.config import REPO_ROOT


def _gen():
    spec = importlib.util.spec_from_file_location("gen", REPO_ROOT / "scripts" / "generate_synthetic.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_workers_reproducible_and_balanced():
    gen = _gen()
    a = gen.generate_workers(random.Random(1))
    b = gen.generate_workers(random.Random(1))
    assert a == b and len(a) == 60
    assert {w["language"] for w in a} == {"hi", "hinglish", "en"}
    assert sum(w["ground_truth_qp"] == gen.WELDING for w in a) == 10
    assert all(w["synthetic"] for w in a)


def test_every_ground_truth_qp_exists_in_corpus():
    from app.services.qp_store import load_corpus

    assert set(_gen().FACTS) <= set(load_corpus())


def test_images_reproducible_with_labels(tmp_path):
    gen = _gen()
    rows1 = gen.generate_images(7, 2, tmp_path / "a")
    rows2 = gen.generate_images(7, 2, tmp_path / "b")
    assert rows1 == rows2 and len(rows1) == 10
    f = rows1[3]["file"]
    assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes()
    assert {r["quality_level"] for r in rows1 if r["defect"] == "good"} == {3}
