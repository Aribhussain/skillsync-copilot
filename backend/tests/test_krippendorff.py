"""Expected values were produced by the reference implementation (`krippendorff` 0.9.0 on
PyPI, GPL - installed only in a scratch environment for verification, never a dependency).
Our implementation matched it to < 1e-15 on 300 random matrices with missing data."""

import pytest

from app.services.krippendorff import alpha

# Krippendorff's canonical reliability-data example, units x coders (None = missing)
EXAMPLE = [
    [1, 1, None, 1],
    [2, 2, 3, 2],
    [3, 3, 3, 3],
    [3, 3, 3, 3],
    [2, 2, 2, 2],
    [1, 2, 3, 4],
    [4, 4, 4, 4],
    [1, 1, 2, 1],
    [2, 2, 2, 2],
    [None, 5, 5, 5],
    [None, None, 1, 1],
    [None, 3, None, None],
]


@pytest.mark.parametrize(
    ("metric", "expected"), [("nominal", 0.743421), ("ordinal", 0.815388), ("interval", 0.849107)]
)
def test_matches_reference_on_canonical_example(metric, expected):
    assert alpha(EXAMPLE, metric) == pytest.approx(expected, abs=1e-6)


def test_perfect_agreement_and_disagreement():
    assert alpha([[0, 0], [1, 1], [2, 2], [3, 3]]) == pytest.approx(1.0)
    assert alpha([[0, 3], [3, 0], [0, 3], [3, 0]]) < 0


def test_undefined_cases():
    assert alpha([[1, None], [None, 2]]) is None  # nothing pairable
    assert alpha([[2, 2], [2, 2]]) is None  # no variation at all
