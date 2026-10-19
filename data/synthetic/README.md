# Synthetic demo data (generated, not committed)

**Everything in this folder is SYNTHETIC.** These are not real workers and not real welds.

Regenerate it with:

```
backend/.venv/Scripts/python scripts/generate_synthetic.py      # Windows
backend/.venv/bin/python scripts/generate_synthetic.py          # macOS / Linux
```

The output is seeded (default seed `26242`) and byte-for-byte reproducible:

- `workers.json`: 60 worker profiles. The Welding QP has 10 and each of the other 10 QPs has 5. Narratives are in Hindi (Devanagari), Hinglish and English, each with a `ground_truth_qp`. Some narratives deliberately overlap trades, e.g. a fitter who "thoda welding bhi" does.
- `weld_images/*.jpg`: 300 procedurally drawn weld coupons, 60 each of good, porosity, undercut, spatter and incomplete. Each has a severity.
- `weld_labels.csv`: the ground truth for each image. `quality_level` runs from 3 (good) through 2 (mild defect) and 1 (severe) to 0 (mostly missing bead).
