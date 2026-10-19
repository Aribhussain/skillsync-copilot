# Solution — SkillSync Co-Pilot

> *We don't replace the assessor — we make every assessor score like the best assessor, and make every certificate audit-proof, even offline in a village workshop.*

## Demo trade

NQR qualification **"Welding", QG-4.5-AU-01811-2024-V1-ASDC**, NSQF 4.5, Automotive Skills Development Council.

| NOS | Name | Marks | Theory / Practical / Viva |
|---|---|---|---|
| ASC/N9819 | Work organization and management | 100 | 30/50/20 |
| ASC/N3120 | Preparation and assembly techniques | 50 | 15/25/10 |
| ASC/N3121 | Welding materials | 50 | 15/25/10 |
| ASC/N3122 | SMAW (111) and GMAW (135) process | 50 | 15/25/10 |
| ASC/N3123 | FCAW-G (136) process | 50 | 15/25/10 |
| ASC/N3124 | GTAW (141) process | 50 | 15/25/10 |
| ASC/N3125 | Finishing, quality assurance and testing | 100 | 30/50/20 |

The total is 450 marks (30% theory, 50% practical, 20% viva). The pass mark is 70% aggregate.

## Six modules

| Module | What it does |
|---|---|
| **M1 — Voice-first "Kaam ki Kahani" declaration** | The worker speaks, types or taps icon cards (Hindi / Hinglish / English). A trade-vernacular lexicon maps shop-floor slang to NSQF terms ("argon ka kaam" → GTAW, "CO2 welding" → GMAW, "electrode / stick" → SMAW). |
| **M2 — NSQF QP mapping engine** | Hybrid retrieval combines BM25, lexicon expansion and a multilingual sentence-embedding re-rank. It returns the top-3 QPs with confidence and a per-PC claim prefill. A BM25 + lexicon "mapper-lite" also runs on the device, offline. |
| **M3 — PC-level evidence plan** | Each PC gets an evidence route: `observe`, `photo`, `viva` or `declaration+spot-check`. Critical and safety PCs are locked to live observation. |
| **M4 — Signed Process–Product–Person capture** | Three guided shots: setup and PPE, the finished weld, and the worker holding a slate with a one-time challenge code. On-device QC checks blur, brightness and framing. Each shot is bound to GPS and time, hashed with SHA-256, signed with ECDSA P-256 on the device, kept in an AES-GCM vault and synced later. The server verifies the signature and runs pHash de-duplication across all evidence. |
| **M5 — Blind-first AI shadow rater** | The assessor scores each PC first, and the AI suggestion is revealed only afterwards. This is enforced server-side. If the gap is large, the assessor must give a reason code. |
| **M6 — Calibration loop + competency profile** | Hidden golden packets measure agreement with Krippendorff's α and give each assessor a private Calibration Index; QA leads get drift heat-maps. The tool produces a per-PC NSQF profile with a Full / Partial / Gap recommendation and bridge modules. After the assessor signs off, it issues a W3C Verifiable Credential with a QR verify page. |

## Where the tool supports vs replaces judgement

| Decision | AI role | Final say |
|---|---|---|
| QP suggestion | Ranks top-3 | Worker + assessor confirm |
| Evidence plan | Rules engine (critical PCs locked) | System rule |
| Evidence authenticity | Flags anomalies | Assessor reviews |
| PC scores | Second opinion, shown after the blind score | Assessor |
| Full / Partial / Fail | Recommends only | Assessor only |
| Certificate | None | Awarding body |

## Integrity and privacy

- A hash-chained, append-only **audit ledger** records every important event. `GET /audit/verify` recomputes the chain.
- A DPDP Act 2023-style **consent screen and consent ledger**.
- **No face templates** are stored. The "Person" shot is kept only as evidence for the assessor to review.
- The local evidence vault is encrypted with **AES-GCM** (WebCrypto, non-extractable key).
