# SkillSync Co-Pilot (macOS / Linux). On Windows use the same targets via npm:
#   npm run setup | lite | test | full:up | full:smoke | full:down
PY := backend/.venv/bin/python

.PHONY: setup lite-up seed test e2e full-up full-smoke full-down

setup:            ## venv + deps, frontend deps, .env
	node scripts/setup.mjs

lite-up:          ## API :8000 + PWA :5173 (SQLite, local files, no Docker)
	node scripts/dev.mjs

seed:             ## demo data for the 5-minute demo (lite mode)
	$(PY) scripts/seed_demo.py

test:             ## backend + frontend unit tests, lint, typecheck
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npx vue-tsc -b && npx eslint . && npx vitest run

e2e:              ## Playwright against the dev servers
	cd frontend && npx playwright test

full-up:          ## Docker full mode: Postgres+pgvector, S3 object store, Redis, Celery, nginx
	docker compose up -d --build --wait

full-smoke:       ## end-to-end checks against the running full stack
	$(PY) scripts/smoke_full.py

full-down:
	docker compose down
