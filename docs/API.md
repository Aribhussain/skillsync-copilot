# API

The live, always-current reference is the interactive OpenAPI UI at **http://localhost:8000/docs** (ReDoc at `/redoc`, schema at `/openapi.json`). This page is a map of it, generated from that schema on 2026-10-20.

- **Auth:** `POST /auth/login` returns a JWT; send it as `Authorization: Bearer <token>`. Roles: `worker`, `assessor`, `qa_lead`, `admin`, enforced per route.
- **Public routes** (no token): `/health`, `/auth/demo-accounts`, `/credentials/{id}` and `/credentials/{id}/verify` (anyone can check a certificate).
- **Blind-first is enforced here, not in the UI:** AI suggestions only come back in the response to the assessor's own blind score, from `/ai-suggestions` (403 before scoring) or from `/scores/{pc_id}/ai-refresh` (403 before scoring).
- **Idempotency:** offline clients send a `client_id` on declarations, assessments and scores; repeats return the original row.
- **Audit:** every state-changing call appends to the hash-chained ledger. `GET /audit/verify` recomputes it.

## System

| Method | Path | What it does |
|---|---|---|
| `GET` | `/health` | Health |

## Auth

| Method | Path | What it does |
|---|---|---|
| `POST` | `/auth/login` | Login |
| `POST` | `/auth/token` | OAuth2 form login (used by the Swagger 'Authorize' button). |
| `GET` | `/auth/me` | Me |
| `GET` | `/auth/demo-accounts` | Demo credentials for the login screen. Disabled when APP_ENV=production. |
| `GET` | `/users` | List Users |

## Audit & consent

| Method | Path | What it does |
|---|---|---|
| `GET` | `/audit/verify` | Recompute the whole hash chain. Any edited, deleted or reordered row breaks it. |
| `GET` | `/audit/entries` | List Audit Entries |
| `GET` | `/consents/notice` | Consent Notice |
| `POST` | `/consents` | Give Consent |
| `GET` | `/consents/me` | Current consent state per purpose (latest row wins) plus the full history. |

## Qualification packs

| Method | Path | What it does |
|---|---|---|
| `GET` | `/qps` | List Qps |
| `GET` | `/qps/{qp_id}` | Read Qp |

## Lexicon

| Method | Path | What it does |
|---|---|---|
| `GET` | `/lexicon` | Get Lexicon |
| `POST` | `/lexicon` | Assessor-confirmed addition: a worker used a term the lexicon didn't know. |
| `GET` | `/lexicon/additions` | List Additions |

## Offline packs

| Method | Path | What it does |
|---|---|---|
| `GET` | `/packs/latest` | QP pack for the device: QPs + BM25 stats + lexicon, for the offline mapper-lite. |
| `GET` | `/packs/version` | Pack Version |

## M1/M2 declaration & mapping

| Method | Path | What it does |
|---|---|---|
| `POST` | `/declarations` | Store the narrative. Idempotent on `client_id`, so offline retries never duplicate. |
| `POST` | `/declarations/preview-map` | Map text without storing it (live preview while the worker speaks). |
| `POST` | `/declarations/{declaration_id}/map` | Top-3 QPs with confidence, matched lexicon terms and a per-PC claim prefill. |
| `GET` | `/declarations/mine` | My Declarations |
| `GET` | `/declarations/{declaration_id}` | Read Declaration |

## Speech

| Method | Path | What it does |
|---|---|---|
| `GET` | `/speech/config` | Speech Config |
| `POST` | `/speech/transcribe` | Transcribe |

## Assessments

| Method | Path | What it does |
|---|---|---|
| `POST` | `/assessments` | The worker confirms a QP (and their claimed PCs); this creates the assessment request. |
| `GET` | `/assessments/mine` | My Assessments |
| `GET` | `/assessments/{assessment_id}` | Read Assessment |
| `GET` | `/assessments/{assessment_id}/plan` | M3: the PC-level evidence plan (route per PC, critical/safety PCs locked) and rubric. |
| `PATCH` | `/assessments/{assessment_id}/plan` | Change the evidence route of an unlocked PC. Critical/safety PCs are refused (409). |
| `POST` | `/assessments/{assessment_id}/start` | Begin the assessment and issue the one-time challenge code for the 'Person' photo. |
| `GET` | `/assessor/queue` | Assessments assigned to me. Calibration (golden) packets look exactly like the rest. |
| `GET` | `/assessor/rubric` | Get Rubric |

## M4 evidence

| Method | Path | What it does |
|---|---|---|
| `POST` | `/devices` | Register this device's ECDSA P-256 public key (idempotent for the same key). |
| `POST` | `/assessments/{assessment_id}/evidence` | Accept a capture packet only if the image hash and the device signature verify. The image comes either as a multipart `file` or as a completed chunked `upload_id`. |
| `GET` | `/assessments/{assessment_id}/evidence` | List Evidence |
| `GET` | `/evidence/{evidence_id}/image` | Evidence Image |
| `POST` | `/uploads` | Start (or resume) a chunked image upload. |
| `GET` | `/uploads/{upload_id}` | Upload Status |
| `PUT` | `/uploads/{upload_id}/chunks/{index}` | Put Chunk |

## M5 blind-first scoring

| Method | Path | What it does |
|---|---|---|
| `POST` | `/assessments/{assessment_id}/scores` | Record the assessor's blind score. Only now is the AI suggestion revealed. |
| `GET` | `/assessments/{assessment_id}/scores` | My Scores |
| `POST` | `/assessments/{assessment_id}/scores/{pc_id}/ai-refresh` | Re-check the AI opinion for a PC this assessor has ALREADY blind-scored, when it was `pending` or `awaiting_photo` at lock time. Blind-first still holds: no score, no AI. |
| `GET` | `/assessments/{assessment_id}/ai-suggestions` | AI suggestions ONLY for PCs this assessor has already scored (blind-first). |
| `PATCH` | `/assessments/{assessment_id}/scores/{pc_id}` | Revise the final score and/or give the reason for a large gap. The blind score never changes. |

## M6 calibration

| Method | Path | What it does |
|---|---|---|
| `GET` | `/calibration/me` | The assessor's own Calibration Index (never other assessors'). |
| `GET` | `/calibration/summary` | QA view: Krippendorff's alpha, trend, assessor x NOS drift, centres, reason codes. |
| `POST` | `/calibration/golden/seed` | Randomly seed golden packets into assessor queues (they are not marked as golden). |

## M6 competency profile

| Method | Path | What it does |
|---|---|---|
| `GET` | `/assessments/{assessment_id}/profile` | Per-PC -> per-NOS NSQF competency profile with a Full / Partial / Gap recommendation. |

## M6 sign-off & credential

| Method | Path | What it does |
|---|---|---|
| `POST` | `/assessments/{assessment_id}/signoff` | The assessor's decision. Nothing else in the system sets `signed_off`: no automatic submission, ever. Requires the assessor's password, every PC scored and every large AI gap explained. A decision that differs from the recommendation needs a justification. |
| `GET` | `/credentials/{credential_id}` | The verifiable credential JSON (public, like any shareable credential). |
| `GET` | `/credentials/{credential_id}/verify` | Public verification for the QR code: checks the Ed25519 proof and the issuer. |
| `GET` | `/credentials/{credential_id}/pdf` | Credential Pdf |
| `GET` | `/credentials/mine/list` | My Credentials |
| `GET` | `/export/sidh/{assessment_id}` | SIDH-style result payload. MOCK schema for the prototype, NOT the official Skill India Digital Hub API (documented in docs/API.md). |

## M6 live consistency study

| Method | Path | What it does |
|---|---|---|
| `GET` | `/studies` | List Studies |
| `POST` | `/studies` | Create Study |
| `GET` | `/studies/{study_id}/task` | The next packet for this rater in `arm`. ON unlocks only after every OFF score is done. |
| `GET` | `/studies/{study_id}/packets/{packet_id}/image` | Packet Image |
| `POST` | `/studies/{study_id}/scores` | Blind score. In the ON arm the AI suggestion is revealed only in this response. |
| `POST` | `/studies/{study_id}/scores/final` | ON arm only: the rater's final score after seeing the AI (the blind score is kept). |
| `GET` | `/studies/{study_id}/results` | Study Results |

