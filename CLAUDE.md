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

## Commands (lite mode)
```
make setup        # venv + pip + npm install
make seed         # seed demo data
make lite-up      # backend :8000 + frontend :5173
make test         # backend + frontend tests
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
- [ ] 9 Blind-first shadow rater
- [ ] 10 Calibration, profile, sign-off, credential → v0.8.0
- [ ] 11 Consistency study
- [ ] 12 Offline hardening + sync
- [ ] 13 Docker full mode / MySQL support
- [ ] 14 CI, demo seed, screenshots, docs → v1.0.0
