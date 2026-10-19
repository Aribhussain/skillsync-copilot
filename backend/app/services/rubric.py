"""Standardised scoring rubric: one 0-3 scale for every PC, with level descriptors and,
for PCs judged from the product photo, synthetic example images of good vs poor welds.

Using the same anchors at every centre is how the tool reduces assessor-to-assessor
variance (PS requirement 3).
"""

from __future__ import annotations

LEVELS = [
    {
        "level": 0,
        "en": "Not demonstrated — could not do it, or did it unsafely.",
        "hi": "नहीं दिखाया — नहीं कर पाए, या असुरक्षित तरीके से किया।",
        "fraction": 0.0,
    },
    {
        "level": 1,
        "en": "Partially — did it with major errors or needed step-by-step help.",
        "hi": "आंशिक — बड़ी गलतियों के साथ या कदम-दर-कदम मदद से किया।",
        "fraction": 0.4,
    },
    {
        "level": 2,
        "en": "Competent — meets the standard without help; minor slips only.",
        "hi": "सक्षम — बिना मदद के मानक पूरा किया; केवल छोटी चूक।",
        "fraction": 0.8,
    },
    {
        "level": 3,
        "en": "Proficient — consistently above the standard; could guide others.",
        "hi": "दक्ष — लगातार मानक से बेहतर; दूसरों को सिखा सकते हैं।",
        "fraction": 1.0,
    },
]

# Example images (synthetic) for PCs judged from the product photo, keyed by ai_signal.
EXAMPLES = {
    "overall": {"good": "/rubric/good.jpg", "poor": "/rubric/porosity.jpg", "poor_label": "porosity"},
    "porosity": {"good": "/rubric/good.jpg", "poor": "/rubric/porosity.jpg", "poor_label": "porosity"},
    "undercut": {"good": "/rubric/good.jpg", "poor": "/rubric/undercut.jpg", "poor_label": "undercut"},
    "spatter": {"good": "/rubric/good.jpg", "poor": "/rubric/spatter.jpg", "poor_label": "spatter"},
    "incomplete": {
        "good": "/rubric/good.jpg",
        "poor": "/rubric/incomplete.jpg",
        "poor_label": "incomplete fusion",
    },
}


def rubric() -> dict:
    return {
        "scale": LEVELS,
        "examples": EXAMPLES,
        "note": "Example images are SYNTHETIC (procedurally drawn).",
    }
