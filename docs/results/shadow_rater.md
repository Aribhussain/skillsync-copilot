# Shadow rater — demo model

> **Demo model trained on synthetic images — not for certification.** Trained and evaluated on procedurally drawn weld images only. These numbers say the pipeline works end to end. They do **not** say how the model would do on real welds.

- Model: `demo-rf-26242-120`, two RandomForests (defect class, quality level 0–3) over 11 OpenCV features
- Training data: 420 synthetic images, with a 180-image hold-out from the same generator run

| Metric | Value |
|---|---|
| Defect accuracy (hold-out) | 95.0% |
| Quality level accuracy (hold-out) | 90.0% |
| Quality level within ±1 (hold-out) | 98.9% |
| Defect accuracy (freshly generated, new seed) | 95.0% |
| Quality level accuracy (new seed) | 90.5% |
| Defect accuracy on the 12 bundled demo samples (captioned) | 100.0% |

## Confusion matrix (hold-out, rows = true, columns = predicted)

| | good | porosity | undercut | spatter | incomplete |
|---|---|---|---|---|---|
| **good** | 33 | 0 | 0 | 0 | 3 |
| **porosity** | 1 | 33 | 2 | 0 | 0 |
| **undercut** | 1 | 0 | 35 | 0 | 0 |
| **spatter** | 0 | 2 | 0 | 34 | 0 |
| **incomplete** | 0 | 0 | 0 | 0 | 36 |

## Feature importance (defect model)

| Feature | Importance |
|---|---|
| spatter | 0.183 |
| pore_area | 0.137 |
| toe_dark_run | 0.105 |
| pores | 0.105 |
| coverage | 0.104 |
| toe_dark | 0.093 |
| lap_var | 0.069 |
| gaps | 0.065 |
| width_cv | 0.058 |
| bead_area | 0.045 |
| bead_contrast | 0.037 |

## Bundled demo samples

| Sample | True | Predicted | Level | p |
|---|---|---|---|---|
| weld_00_good.jpg | good | good | 3 | 0.95 |
| weld_01_good.jpg | good | good | 3 | 0.93 |
| weld_02_good.jpg | good | good | 3 | 0.94 |
| weld_03_good.jpg | good | good | 3 | 0.83 |
| weld_04_porosity.jpg | porosity | porosity | 1 | 0.99 |
| weld_05_porosity.jpg | porosity | porosity | 2 | 1.00 |
| weld_06_undercut.jpg | undercut | undercut | 1 | 0.99 |
| weld_07_undercut.jpg | undercut | undercut | 2 | 0.79 |
| weld_08_spatter.jpg | spatter | spatter | 1 | 0.81 |
| weld_09_spatter.jpg | spatter | spatter | 2 | 0.98 |
| weld_10_incomplete.jpg | incomplete | incomplete | 1 | 0.99 |
| weld_11_incomplete.jpg | incomplete | incomplete | 2 | 0.98 |

## Limits

- The synthetic generator draws every defect in one stylised way, so near-perfect scores are expected and uninformative about real welds, lighting, angles and metals.
- In the product the model is a **second opinion shown only after the assessor's blind score**. It never decides a score. Real deployment needs a model trained on labelled field photos, swapped in behind the `ShadowRater` interface.
