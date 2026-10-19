# QP corpus

One JSON file per Qualification Pack: QP → NOS → PCs. The loader is `backend/app/services/qp_store.py`, which validates every file at startup.

| File | Source |
|---|---|
| `welding_QG-4.5-AU-01811-2024-V1-ASDC.json` | **Official.** The NOS, PC text and theory/practical/viva marks come from the NQR Qualification File (`nqr.gov.in/qualification/file/QFile_Welding.pdf`, approved 06-02-2024). `evidence_hint`, `critical`, `safety` and `ai_signal` are SkillSync annotations. |
| all other files | **`drafted-for-demo`.** Realistic structure so the mapper has real competition, including 3 other welding QPs. Codes are indicative and not verified against NQR. |

PC fields: `code`, `text`, `marks{theory,practical,viva}` (or `weight`, which the loader distributes), `critical`, `safety`, `evidence_hint` (`observe|photo|viva|declaration`), `ai_signal` (which image-based signal the demo shadow rater may comment on, or `null`).
