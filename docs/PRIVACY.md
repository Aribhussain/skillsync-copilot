# Privacy and the DPDP Act 2023

SkillSync Co-Pilot handles personal data about workers: their work story, voice-derived text, photos and assessment results. This page describes what the prototype actually does, mapped to the principles of India's Digital Personal Data Protection Act, 2023. It is a design note for a hackathon prototype, **not legal advice or a compliance certificate**. A production deployment needs a DPDP review by the data fiduciary (the awarding body or its assessment agency).

## What is collected, and why

| Data | Purpose (consent key) | Where it lives | Notes |
|---|---|---|---|
| Work story (typed, or voice turned into text) | `rpl_assessment`, plus `voice_processing` for voice | `declarations` table; on the device in IndexedDB until synced | Only the **text** is kept. Audio is never uploaded or stored. The browser's speech engine does the transcription. |
| QP mapping result, claimed PCs | `rpl_assessment` | `declarations.mapping`, `assessments` | Explainable: matched terms are stored with the result. |
| Three evidence photos (Process, Product, Person + challenge-code slate) | `evidence_capture` | Encrypted on the device (AES-GCM, non-extractable WebCrypto key) until synced; then `storage/evidence/` or the S3 store | Signed on the device (ECDSA P-256), with time and GPS. **No face templates** are created or stored; the Person shot is evidence for a human to look at, not biometrics. |
| Scores, AI suggestions, reason codes, decision | `rpl_assessment` | `pc_scores`, `ai_analyses`, `assessments` | The blind score is immutable; revisions keep the original. |
| Credential | `rpl_assessment` | `credentials`; public verify page | Shows the name, qualification, result and competent NOS. It contains no photos, GPS or scores per PC. |

## How the Act's principles map to the code

- **Notice in plain language, in the worker's language** (s.5). `GET /consents/notice?lang=hi|en` returns the notice ([consent.py](../backend/app/services/consent.py)), and the worker app shows it before anything is collected.
- **Consent is specific to each purpose and provable** (s.6).
  - Each purpose is consented to separately.
  - Every consent row stores the SHA-256 of the exact notice text and its version (`2026-10`), so it can be proved what the worker agreed to.
  - Consent events also go into the hash-chained audit ledger.
- **Consent is enforced on the server, not only in the UI.**
  - Declarations need `rpl_assessment`.
  - Evidence uploads need the **worker's** current `evidence_capture` consent. Without it the API returns 409, and the rejection is audited as `evidence.rejected` / `no_consent`.
  - Offline, the photo stays in the encrypted device vault and the outbox marks it as failed with the reason, so it is not silently lost.
- **Withdrawal is as easy as giving consent** (s.6(4)).
  - `POST /consents` with `"granted": false` records a withdrawal, and the latest row wins.
  - Withdrawing `evidence_capture` stops any further photo uploads for that worker.
  - `GET /consents/me` shows the current state and the full history.
- **Purpose limitation and data minimisation** (s.4, s.8(7)).
  - No audio and no face templates are stored.
  - GPS is rounded to 6 decimals in the signed packet and used only for integrity flags.
  - Integrity checks produce **flags for the assessor**, never automatic rejections.
- **Accuracy** (s.8(3)). The worker confirms the QP and can untick wrongly claimed PCs. The assessor can revise final scores, while the blind score and the audit trail keep the history.
- **Security safeguards** (s.8(5)).
  - Passwords are hashed with bcrypt, sessions use JWT, and role-based access control applies per route.
  - Evidence is encrypted on the device and its signature is verified on the server.
  - The ledger is hash-chained and tamper-evident (`GET /audit/verify`).
  - The credential is signed with Ed25519, and the issuer key is kept outside git.
- **Accountability.** Every important write appends to the audit ledger with actor, action and payload hash. QA leads can verify the chain from the dashboard.
- **Children's data** (s.9). RPL candidates are adults. A production system should verify age at enrolment; the prototype does not.

## What the prototype does NOT do yet (honest gaps)

- **Rights requests are not self-serve.** The notice promises access, correction and deletion, but there is no worker-facing "download my data" or "delete my data" flow; an admin would do it in the database. A production build needs both, plus a grievance officer contact (s.8(10), s.11–13).
- **No retention schedule is enforced.** Evidence and declarations are kept until deleted. A production policy would delete raw photos after certification plus an appeal window, keeping only hashes in the ledger.
- **Erasure and the hash chain.** The ledger stores payload *hashes* and IDs rather than raw personal data, so erasing a record doesn't break the chain. This is by design but untested as a full erasure workflow.
- **Data location** depends on where the operator deploys it; nothing in the code sends data outside the deployment.
- **The demo accounts and JWT secret** in `.env.example` are local defaults and must be changed for any real use.
- **The browser speech engine.** Some browsers send audio to their vendor's speech service. Production should use an on-device engine (e.g. Vosk) or Bhashini under a data-processing agreement; the Bhashini adapter is only a scaffold.

## Synthetic data

All demo workers beyond `worker1` and `worker2`, all golden packets and all weld images are **synthetic**, generated by [`scripts/generate_synthetic.py`](../scripts/generate_synthetic.py). No real worker data is in this repository.
