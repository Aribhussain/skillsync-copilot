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

**Done:** Phases 0–13 (tags v0.1.0, v0.3.0, v0.5.0, v0.8.0). Phase 13 added:
- Docker full mode (`docker-compose.yml`): Postgres 16 + pgvector, SeaweedFS as the S3 store (MinIO is AGPL and no longer on Docker Hub), Redis, the API, a Celery worker, and nginx serving the PWA on :8080.
- Env-switched storage and queue adapters, plus `PgVectorIndex`.
- `scripts/smoke_full.py` and `npm run e2e:docker` (all passed on the live stack, which was then torn down).
- The `pending` AI status with `/ai-refresh` polling, and two real bugs fixed (the Postgres seq identity, the auto-train defaults).
- `scripts/setup_db.py` for MySQL / SQL Server: offline-tested only, by the user's choice.
- A Makefile, plus root `package.json` scripts that work on Windows.

**Resume at: Phase 14.**
- CI `.github/workflows/ci.yml`: ruff, pytest, eslint, vue-tsc, vitest, build, Playwright (CI installs chromium), and e2e:pwa.
- `scripts/seed_demo.py` (the Makefile `seed` target already points at it).
- `scripts/screenshots.ts`: 4 screenshots at 1280×800 and 390×844 into `docs/screenshots`.
- README (pitch, PS→module→code table, Mermaid, quick start, demo accounts, 5-minute demo, support-vs-replace, results, licences), `docs/DEMO_SCRIPT.md`, `docs/API.md`, `docs/PRIVACY.md`.
- Tag `v1.0.0` and create a GitHub release with the screenshots.

**Open issues / decisions to remember**
- MySQL / SQL Server have not been run live: only the offline DDL and `setup_db.py` planning tests exist (user's choice). The Docker image has no torch, so the embedding re-rank is off in full mode.
- `v0.3.0` points at a commit that had ruff E501 findings in `ml/eval_mapping.py`, fixed in the next commit. The tag was deliberately not moved (see DECISIONS.md).
- pHash reuse threshold is 6 (measured). Crops and rotations evade it, and about 1% of distinct *synthetic* welds collide. Documented.
- The shadow rater and the golden consensus are SYNTHETIC; label them that way everywhere.
- The Bhashini adapter is a scaffold only (501). The Vosk offline speech adapter isn't built yet (Phase 12; ask before downloading its model).
- Node may not be on PATH in old terminals. In Git Bash use `export PATH="$PATH:/c/Program Files/nodejs"`.
- `ml/models/shadow_rater.joblib` is git-ignored. The backend trains it on first start (about 9 s, same defaults as `ml/train_shadow_rater.py`) if it's missing.
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
Shortcuts (any OS, from the repo root): `npm run setup`, `npm run lite` (API + PWA together), `npm test`.
macOS/Linux: `make setup | lite-up | test | full-up | full-smoke | full-down`.

## Docker full mode
```
docker compose up -d --build --wait          # or npm run full:up; app :8080, API :8000
backend/.venv/Scripts/python scripts/smoke_full.py
cd frontend && npm run e2e:docker            # browser e2e against :8080
docker compose down -v                       # -v also deletes the data volumes
```

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
- [x] 10 Calibration, profile, sign-off, credential → v0.8.0
- [x] 11 Consistency study
- [x] 12 Offline hardening + sync
- [x] 13 Docker full mode / MySQL support
- [ ] 14 CI, demo seed, screenshots, docs → v1.0.0
