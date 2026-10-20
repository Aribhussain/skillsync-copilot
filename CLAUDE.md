# CLAUDE.md — SkillSync Co-Pilot project memory

SIH 2026 · PS 26242 · AI-assisted RPL skill assessment (MSDE). Demo trade: **Welding QG-4.5-AU-01811-2024-V1-ASDC (NSQF 4.5)**.

## Non-negotiables
- The AI **supports** the assessor and never replaces them. Final scores, the Full/Partial/Gap decision and sign-off belong to the human assessor.
- **Blind-first is enforced server-side**: no API response may contain an AI suggestion for a PC before that assessor's blind score for that PC exists.
- **No auto sign-off.** A credential is issued only by `POST /assessments/{id}/signoff` with the assessor's re-entered password.
- Critical/safety PCs are always routed to **live observation** and can't be downgraded.
- Anything synthetic or simulated is labelled in the UI and docs ("Synthetic demo data", "Demo model trained on synthetic images", "SIMULATED").
- No secrets in git (`.env` is ignored; `.env.example` holds safe demo defaults).
- Only MIT / Apache-2.0 / BSD / ISC / PSF dependencies. **No AGPL/GPL** (no Ultralytics).
- Commit history is real: no backdating, no history rewrites.

## Layout
```
frontend/   Vue 3 + Vite + TS PWA (worker, assessor, QA)
backend/    FastAPI app: app/api (routers), app/core (config, db, security),
            app/models (SQLModel), app/services (domain logic), app/ml (model wrappers)
ml/         training / evaluation scripts, ml/models (trained artefacts)
data/       qp_corpus/, lexicon/, synthetic/ (generated), golden_packets/
scripts/    seed, synthetic data, study simulation, screenshots, db setup
docs/       documentation, results/, screenshots/
```

## Conventions
- Python 3.11, venv at `backend/.venv` (`py -3.11 -m venv backend/.venv`). Lint with `ruff`, test with `pytest`.
- Database is chosen only by `DATABASE_URL`. Keep models portable: SQLAlchemy `JSON`, `String(length)` for indexed text, no ARRAY/JSONB.
- Schema changes go through Alembic (`backend/alembic`). Tests use a temp SQLite DB.
- Every important write appends to the hash-chained audit ledger (`app.services.audit.record`).
- Frontend: Composition API + `<script setup lang="ts">`, Pinia stores, i18n keys in `src/i18n/{en,hi}.json`.
- Offline-first: write to Dexie first, then enqueue in the outbox; the sync engine pushes with idempotency keys.
- Conventional Commits; push after every commit; tag milestones.
- Playwright uses the locally installed Brave (`PLAYWRIGHT_BROWSER_PATH`) with a fresh temp profile; never download browsers locally (`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`). CI uses `npx playwright install chromium`.

## Progress / Resume here  (updated 2026-10-20)

The full original brief is in [docs/BUILD_PROMPT.md](docs/BUILD_PROMPT.md); the session clarifications are at its end.

**Done:** Phases 0–9 (tags v0.1.0, v0.3.0, v0.5.0), plus the first of the four Phase 10 commits:
`a883a79 feat(calibration): golden packets, Krippendorff alpha and calibration index`.

**Resume at: Phase 10, commit 2 of 4.**
1. `feat(dashboard)`: QA dashboard in `frontend/src/views/QaHome.vue`, built with vue-echarts 8 / echarts 6 (`import VChart from 'vue-echarts'` + `use()` from `echarts/core`). It reads `GET /calibration/summary` and `GET /audit/verify` (for the "chain verified" badge). Panels:
   - KPI tiles: alpha blind, alpha final, alpha decision, AI agreement.
   - Alpha trend line: blind vs final, one axis.
   - Assessor × NOS heat-map: diverging scale with a grey midpoint (lenient vs severe).
   - Centre comparison bars and reason-code bars.
   - A table of assessor indices and a "Seed golden packets" button (`POST /calibration/golden/seed`).

   Also show the assessor's own index (`GET /calibration/me`) on `AssessorHome`. Follow the dataviz skill: validate the palette with its script and add tooltips.
2. `feat(profile)`: competency profiler. Level → fraction is {0: 0, 1: 0.4, 2: 0.8, 3: 1.0}. Each PC earns marks × fraction, using its own T/P/V marks. NOS results are ≥ 70% competent, 40–70% partial, < 40% gap. The overall result is Full only if the aggregate is ≥ 70% and no critical PC scored below 2; otherwise Partial or Gap. Gap NOS get their `bridge_module` from the QP JSON. Add an endpoint and a UI.
3. `feat(credential)`: sign-off with password re-entry, refused if any `reason_required` score lacks a reason; never automatic. Then:
   - An Ed25519 server key (git-ignored), a W3C VC 2.0 JSON with a `did:key` issuer, the public `/verify/{credential_id}` API and page, and a reportlab PDF with a QR code.
   - `GET /export/sidh/{assessment_id}` (a mock schema, documented as such).

   Tag `v0.8.0` after this commit.

**Next phases after 10:** 11 consistency study → 12 offline hardening → 13 Docker full mode + MySQL `setup_db.py` (ask the user for the MySQL root password at runtime, or let them run it) → 14 CI, `seed_demo.py`, screenshots, README, `v1.0.0` release.

**Open issues / decisions to remember**
- The `Makefile` doesn't exist yet (Phase 14), so the `make …` commands in this file are planned, not working. Use the manual commands below.
- `v0.3.0` points at a commit that had ruff E501 findings in `ml/eval_mapping.py`, fixed in the next commit. The tag was deliberately not moved (see DECISIONS.md).
- pHash reuse threshold is 6 (measured). Crops and rotations evade it, and about 1% of distinct *synthetic* welds collide. Documented.
- The shadow rater and the golden consensus are SYNTHETIC; label them that way everywhere.
- The Bhashini adapter is a scaffold only (501). The Vosk offline speech adapter isn't built yet (Phase 12; ask before downloading its model).
- Node may not be on PATH in old terminals. In Git Bash use `export PATH="$PATH:/c/Program Files/nodejs"`.
- `ml/models/shadow_rater.joblib` is git-ignored. The backend trains it on first start (~15 s) if it's missing, or run `python ml/train_shadow_rater.py`.
- When piping test output, check `PIPESTATUS` / use `set -o pipefail`. Run `ruff format` before `ruff check`.

## Commands (lite mode; Windows paths)
```
# one-time
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements-dev.txt     # + requirements-embeddings.txt (optional, ~700 MB)
cd frontend && npm install          # PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 is set in .env.example
python scripts/generate_synthetic.py  # (any Python with the backend venv) synthetic workers + weld images
python ml/train_shadow_rater.py       # optional: the server trains it on first start anyway

# run (two terminals)
cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000    # API + /docs
cd frontend && npm run dev                                                         # http://localhost:5173

# tests
cd backend && .venv/Scripts/python -m pytest
cd frontend && npx vue-tsc -b && npx eslint . && npx vitest run && npx playwright test   # e2e drives Brave
```
Planned `make setup / seed / lite-up / test` targets arrive in Phase 14.

## Phase checklist
- [x] 0 Environment setup
- [x] 1 Repository bootstrap
- [x] 2 Backend core (app, auth/RBAC, audit ledger, consent) → v0.1.0
- [x] 3 Data foundation (QP corpus, lexicon, synthetic generator)
- [x] 4 M1+M2 mapping engine + eval + QP pack → v0.3.0
- [x] 5 Frontend foundation
- [x] 6 Worker declaration + mapper-lite + outbox
- [x] 7 Evidence plan + assessor checklist
- [x] 8 Signed P-P-P capture + integrity → v0.5.0
- [x] 9 Blind-first shadow rater
- [ ] 10 Calibration, profile, sign-off, credential → v0.8.0
- [ ] 11 Consistency study
- [ ] 12 Offline hardening + sync
- [ ] 13 Docker full mode / MySQL support
- [ ] 14 CI, demo seed, screenshots, docs → v1.0.0
