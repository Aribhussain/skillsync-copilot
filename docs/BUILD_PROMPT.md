# Build Prompt — SkillSync Co-Pilot (SIH 2026 · PS 26242) Working Prototype

> This is the original build prompt the prototype is being built from, saved verbatim so
> the work can be resumed in a new session. Clarifications the user gave during the build
> are listed at the end under "Session clarifications".

---

## 0. Your role and ground rules

You are the lead engineer building a **working, demo-ready prototype** of **SkillSync Co-Pilot**, our Smart India Hackathon 2026 entry for **Problem Statement 26242: "AI-Assisted Skill Assessment Tool for Recognition of Prior Learning (RPL)"** (Ministry of Skill Development & Entrepreneurship, theme: Smart Education, category: Software).

You will set up the dev environment, build the full-stack app, and **commit and push to a new GitHub repository after every meaningful chunk**, so the repo history shows a real, step-by-step development process.

Ground rules:
1. **Plan first.** Before writing code, read this whole prompt, create `CLAUDE.md` (project memory) and a todo list of all phases. Keep the todo list updated as you go.
2. **One phase at a time.** For each phase: implement → run it → run its tests → fix → commit → push. Never commit code that doesn't run or tests that fail.
3. **Small, honest commits.** Use Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`, `refactor:`). Push after every commit (`git push`). **Never backdate commits, rewrite history, or fake timestamps** — the history must reflect real work done now.
4. **Ask before system-level installs** (anything needing admin/sudo, or large downloads > 500 MB). Project-level installs (npm/pip into the project venv) don't need asking.
5. **No secrets in git.** Use `.env.example`; real `.env` stays ignored.
6. **Everything must run on a normal laptop without Docker** ("lite mode") — Docker is an optional "full mode".
7. **Be truthful in the UI and docs.** Anything synthetic, simulated, or a demo model must be labelled as such ("Synthetic demo data", "Demo vision model — not for certification").
8. Only use permissively licensed dependencies (MIT / Apache-2.0 / BSD / ISC). **No AGPL** (e.g. do not use Ultralytics YOLOv8).
9. If something in this prompt is impossible on this machine, say so, pick the closest working alternative, note it in `docs/DECISIONS.md`, and continue.

---

## 1. Problem statement (summary)

India's informal workforce learned trade skills on the job and has no credential. NCVET's Recognition of Prior Learning (RPL) certifies them against NSQF levels, but RPL assessment today is **manual, slow to scale, inconsistent across assessors and locations, and hard to schedule** for workers who can't take time off. The PS asks for an AI-assisted RPL tool that:

1. Guides a worker through a **structured self-declaration** of prior experience, **auto-mapped to the closest NSQF qualification pack(s)**.
2. Supports **practical skill evaluation** with guided task checklists and, where feasible, **image/video assessment aids** that help assessors score consistently.
3. **Standardises scoring rubrics** across assessors and locations to reduce evaluator-to-evaluator variance.
4. Generates an **NSQF-aligned competency profile and certification recommendation for assessor sign-off** (supports, never replaces, the human assessor).
5. Works in **low-connectivity settings** with offline capture and later sync.

Expected outcomes:
- A working workflow from self-declaration to the assessor scoring interface, for at least one trade.
- An NSQF QP mapping engine.
- Evidence of consistency improvement (inter-assessor agreement).
- An offline-capable mobile/web interface.
- A clear statement of where the tool supports vs replaces assessor judgement.

Real-world evidence to cite in docs:
- The CAG Performance Audit Report No. 20 of 2025 on PMKVY found the **same photographs reused as assessment evidence across states**.
- Over 91% of India's employment is informal.

---

## 2. Our solution — SkillSync Co-Pilot

**One-liner:** *We don't replace the assessor — we make every assessor score like the best assessor, and make every certificate audit-proof, even offline in a village workshop.*

**Demo trade:** Welding — NQR qualification **"Welding", QG-4.5-AU-01811-2024-V1-ASDC, NSQF 4.5, Automotive Skills Development Council**. It has 7 NOS:

| NOS | Name | Marks | Theory / Practical / Viva |
|---|---|---|---|
| ASC/N9819 | Work organization and management | 100 | 30/50/20 |
| ASC/N3120 | Preparation and assembly techniques | 50 | 15/25/10 |
| ASC/N3121 | Welding materials | 50 | 15/25/10 |
| ASC/N3122 | SMAW (111) and GMAW (135) process | 50 | 15/25/10 |
| ASC/N3123 | FCAW-G (136) process | 50 | 15/25/10 |
| ASC/N3124 | GTAW (141) process | 50 | 15/25/10 |
| ASC/N3125 | Finishing, quality assurance and testing | 100 | 30/50/20 |

Total 450 marks (30% theory, 50% practical, 20% viva); pass at 70% aggregate.

### Six modules (all must work in the prototype)

- **M1 — Voice-first "Kaam ki Kahani" declaration**
  - The worker speaks (or types, or taps icon cards) about their work in Hindi, Hinglish or English.
  - A **trade-vernacular lexicon** maps shop-floor slang to NSQF terms, e.g. "argon ka kaam" → GTAW, "CO2 welding" → GMAW, "electrode / stick" → SMAW.
- **M2 — NSQF QP mapping engine**
  - Hybrid retrieval: BM25 + lexicon expansion + multilingual sentence embeddings re-rank over a QP corpus.
  - Returns the **top-3 QPs with confidence** and a **per-PC claim prefill** (which performance criteria the worker claims).
  - A lightweight BM25 + lexicon version also runs **on-device, offline**.
- **M3 — PC-level evidence plan**
  - Every performance criterion (PC) gets an evidence route: `observe` | `photo` | `viva` | `declaration+spot-check`.
  - **Critical / safety PCs are locked to live observation** and cannot be downgraded.
- **M4 — Signed "Process–Product–Person" capture**
  - The guided capture has three shots:
    - **Process:** setup and PPE.
    - **Product:** the finished weld.
    - **Person:** the worker holding a slate with a **one-time challenge code**.
  - On-device quality checks: blur, brightness, framing.
  - Each capture is bound to GPS and a timestamp, hashed with SHA-256 and **signed on the device (WebCrypto ECDSA P-256)**, then stored in an encrypted local vault and synced later.
  - The server verifies the signature and runs **perceptual-hash (pHash) de-duplication** across all evidence, flagging reuse.
- **M5 — Blind-first AI shadow rater**
  - The assessor scores each PC **first**. Only after they submit is the AI suggestion revealed.
  - **Enforce this server-side**: the API must never return the AI suggestion before the assessor's score for that PC exists.
  - If the gap is above a threshold, the assessor must pick a **reason code**.
- **M6 — Calibration loop + competency profile**
  - Pre-graded **golden packets** are seeded into assessors' queues.
  - Agreement is measured with **Krippendorff's α**; each assessor gets a private **Calibration Index** plus drift heat-maps for QA leads.
  - Output: a per-PC NSQF competency profile with a **Full / Partial / Gap** recommendation and bridge modules.
  - The **assessor must sign off**, and only then is a **W3C Verifiable Credential (JSON) with a QR verify page** issued.

### Where the tool supports vs replaces judgement (must appear in UI and docs)

| Decision | AI role | Final say |
|---|---|---|
| QP suggestion | Ranks top-3 | Worker + assessor confirm |
| Evidence plan | Rules engine (critical PCs locked) | System rule |
| Evidence authenticity | Flags anomalies | Assessor reviews |
| PC scores | Second opinion, shown after blind score | Assessor |
| Full / Partial / Fail | Recommends only | Assessor only |
| Certificate | None | Awarding body |

### Integrity and privacy

- Hash-chained, append-only **audit ledger** for every important event, with a `/audit/verify` endpoint.
- DPDP Act 2023-style **consent screen and consent ledger**.
- No face templates are stored.
- The local vault is encrypted with AES-GCM via WebCrypto.

---

## 3. Target architecture

```
L1 Field device (PWA, offline-first)
   Worker app · Assessor app · speech · mapper-lite (BM25+lexicon) · capture QC
   capture signer (SHA-256 + ECDSA) · encrypted IndexedDB vault + outbox
        │  sync when online (outbox → REST)        ▲ sync-down packs (QPs, lexicon, golden packets)
L2 Sync & gateway: FastAPI · JWT/RBAC · signature verify · consent ledger · task runner
L3 AI & scoring services (Python):
   1 QP mapping · 2 evidence plan · 3 evidence integrity (pHash/EXIF/time)
   4 AI shadow rater · 5 calibration (Krippendorff α) · 6 competency profiler
L4 Data & audit: SQLite (default) | my installed MySQL / SQL Server | Postgres+pgvector (Docker only) · local FS | MinIO · hash-chained audit ledger
L5 Human gate & outputs: assessor sign-off → W3C VC + QR verify · SIDH-style export API · calibration dashboard
```

### Tech stack (use these unless impossible; record any change in `docs/DECISIONS.md`)

**Frontend:**
- Vue 3 + Vite + TypeScript
- Tailwind CSS
- Pinia, Vue Router, vue-i18n (en + hi)
- `vite-plugin-pwa` (Workbox)
- Dexie.js (IndexedDB)
- Apache ECharts (`vue-echarts`)
- `qrcode`
- Vitest
- Playwright

**Speech:**
- Online: browser Web Speech API (`hi-IN`, `en-IN`) by default. A pluggable adapter for **Bhashini ASR** activates only if `BHASHINI_API_KEY` is set.
- Offline: an optional `vosk-browser` adapter with a script that downloads the small Hindi model on request (ask before downloading).
- Always available: typed input and icon-card fallback.

**Backend:**
- Python 3.11+, FastAPI, Uvicorn
- SQLModel (SQLAlchemy) + Alembic
- Pydantic v2
- `python-jose` or PyJWT, passlib/bcrypt
- `cryptography` (ECDSA verify, Ed25519 VC signing)
- `rank-bm25`, `sentence-transformers`
  - Model: `paraphrase-multilingual-MiniLM-L12-v2`, downloaded lazily. If unavailable, fall back to BM25-only and say so in the UI.
- `imagehash`, Pillow, `opencv-python-headless`
- `scikit-learn`, numpy, pandas
- `krippendorff`
- `reportlab` (PDF profile)
- pytest, httpx, ruff

**Full mode (Docker, optional):**
- PostgreSQL 16 + pgvector
- MinIO
- Redis + Celery

**Lite mode (default):**
- SQLite, local `storage/`, FastAPI BackgroundTasks

**DevOps:**
- Docker Compose
- GitHub Actions (lint + tests)
- Makefile or `justfile`, plus cross-platform npm scripts

### 3a. Database strategy (important — overrides anything above that says PostgreSQL)

The data layer must be **database-agnostic through SQLModel/SQLAlchemy + Alembic**. Choose the database purely by `DATABASE_URL` in `.env`.

| Mode | DATABASE_URL example | Install needed |
|---|---|---|
| **Lite (default)** | `sqlite:///./storage/skillsync.db` | None |
| My installed **MySQL 8** | `mysql+pymysql://skillsync:<pwd>@localhost:3306/skillsync` | `pip install pymysql cryptography` |
| My installed **SQL Server** | `mssql+pyodbc://skillsync:<pwd>@localhost/skillsync?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes` | `pip install pyodbc`; Microsoft ODBC Driver 18 (ask before installing) |
| Docker full mode (optional) | `postgresql+psycopg://...` | Docker only, never a native install |

Rules:
- Build and demo on **SQLite first**. After Phase 4 works, add a `scripts/setup_db.py` that creates the `skillsync` database and user on whichever server I have (ask me for the root/admin password at runtime; never store it), then runs Alembic migrations.
- Use only portable column types:
  - JSON is stored via SQLAlchemy `JSON` (works on SQLite, MySQL and SQL Server).
  - No Postgres-only types (ARRAY, JSONB) in shared models.
  - Use `String(length)` for indexed text columns, because MySQL and SQL Server need lengths.
- **Vector search without pgvector:**
  - Store QP/PC embeddings as JSON or float blobs in the database.
  - Load them into a numpy matrix in memory at startup (the corpus is tiny, a few thousand vectors) and do cosine similarity in numpy.
  - Put this behind a `VectorIndex` interface. pgvector is used only if running Docker full mode.
- Add a test matrix in CI with SQLite. Locally, run the test suite once against my real MySQL/SQL Server and record the result in `docs/DECISIONS.md`.

---

## 4. Phase 0 — Environment setup (do this first, no commits yet)

1. Detect the OS (Windows / macOS / Linux) and shell. Use the right package manager: `winget` on Windows, `brew` on macOS, `apt` on Linux.
2. Check, and install if missing (**ask me before each system-level install**):
   - Git (≥ 2.40). Configure `user.name` / `user.email` if unset (ask me for the values).
   - GitHub CLI `gh`. Then run `gh auth status`; if not logged in, run `gh auth login` and wait for me to finish the browser flow.
   - Node.js 20 LTS or newer, with npm.
   - Python 3.11 or 3.12, plus `venv` (or `uv` if already installed).
   - Docker Desktop: **already installed on my PC.** Verify with `docker --version` and `docker compose version`, and check that the engine is running.
     - Do NOT use Docker during day-to-day development; build and test in lite mode (SQLite).
     - Use Docker only in Phase 13 for full mode, and fully test it there.
     - Lite mode must always keep working without Docker.
   - **Database: do NOT install PostgreSQL.** I don't have it and don't need it.
     - The default database is **SQLite**. It ships with Python, so there's nothing to install.
     - I already have an official SQL server installed (either **MySQL** or **Microsoft SQL Server**). Detect which one:
       - MySQL: `mysql --version`, or a `MySQL80`/`MySQL` Windows service.
       - SQL Server: `sqlcmd -?`, or an `MSSQLSERVER`/`SQLEXPRESS` service.
     - Then tell me what you found. See section 3a for how it's used.
3. Install these VS Code extensions with `code --install-extension <id>`. Skip any already installed and tell me if the `code` CLI isn't on PATH.
   - `Vue.volar`
   - `ms-python.python`
   - `ms-python.vscode-pylance`
   - `charliermarsh.ruff`
   - `dbaeumer.vscode-eslint`
   - `esbenp.prettier-vscode`
   - `bradlc.vscode-tailwindcss`
   - `ms-azuretools.vscode-docker`
   - `eamodio.gitlens`
   - `ms-playwright.playwright`
   - `humao.rest-client`
   - `mtxr.sqltools`
   - `mtxr.sqltools-driver-sqlite`
   - `yzhang.markdown-all-in-one`
   - `bierner.markdown-mermaid`
4. Print a short environment report (versions of everything) and save it later as `docs/ENVIRONMENT.md`.

---

## 5. Phase 1 — Repository bootstrap (commit + push)

1. Create the project folder `skillsync-copilot` (if the name is taken locally or on GitHub, use `skillsync-copilot-sih26242`).
2. Create these files:
   - `README.md` (skeleton)
   - `LICENSE` (MIT)
   - `.gitignore` (Node, Python, `.env`, `storage/`, models, `*.db`)
   - `.editorconfig`
   - `.env.example`
   - `CLAUDE.md` (project conventions + phase checklist)
   - `docs/PROBLEM_STATEMENT.md` (section 1)
   - `docs/SOLUTION.md` (section 2, including the support-vs-replace table)
   - `docs/ARCHITECTURE.md` (Mermaid diagram of section 3)
   - `docs/DECISIONS.md`
3. Use this monorepo layout:
   ```
   skillsync-copilot/
     frontend/        Vue PWA (worker + assessor + QA dashboard)
     backend/         FastAPI app (app/api, app/core, app/models, app/services, app/ml)
     ml/              training/eval scripts (shadow-rater model, mapping eval, consistency study)
     data/            qp_corpus/, lexicon/, synthetic/ (generated), golden_packets/
     scripts/         seed, download-models, screenshots, simulate-study
     docs/            all documentation + docs/screenshots/
     .github/workflows/
     docker-compose.yml
     Makefile
   ```
4. `git init -b main`, first commit `chore: bootstrap SkillSync Co-Pilot monorepo`.
5. Run `gh repo create <name> --public --source=. --remote=origin --push`, with description "SkillSync Co-Pilot — AI-assisted, assessor-calibrated, offline-first RPL assessment (SIH 2026 PS 26242)". Add topics: `sih2026`, `rpl`, `nsqf`, `fastapi`, `vue`, `pwa`, `offline-first`.
6. Print the repo URL.

---

## 6. Build phases (each bullet group ends with a commit + push; tag milestones)

Every phase must end with a green run of its tests. Add or extend tests in every phase.

### Phase 2 — Backend core

1. FastAPI app factory, settings (pydantic-settings, `.env`), SQLModel engine (SQLite default, Postgres via `DATABASE_URL`), and a `/health` endpoint.
2. Auth: JWT login, roles `worker`, `assessor`, `qa_lead`, `admin`, and an RBAC dependency.
3. Seed demo users:
   - `worker1`, `worker2`
   - `assessor1`, `assessor2`, `assessor3`
   - `qa1`
   - `admin`

   Passwords come from `.env.example` defaults and are shown on the login screen as "demo accounts".
4. **Audit ledger service:** every write appends `{seq, ts, actor, action, payload_hash, prev_hash, hash}`. `GET /audit/verify` recomputes the chain. Add a test that tampering with one row breaks verification.
5. **Consent ledger** model + endpoint.

- Commits: `feat(backend): FastAPI core, settings and health check` → `feat(auth): JWT auth with role-based access` → `feat(audit): hash-chained audit ledger with verify endpoint`

### Phase 3 — Data foundation

1. **QP corpus** (`data/qp_corpus/*.json`). Schema: QP → NOS → PCs.
   - PC fields: `id`, `text`, `weight`, `critical`, `safety`, `evidence_hint`.
   - Include the **Welding QG-4.5-AU-01811-2024-V1-ASDC** QP with all 7 NOS above.
   - First try to fetch `https://nqr.gov.in/qualification/file/QFile_Welding.pdf` and extract details. If that's not possible, draft realistic PCs (6–10 per NOS) and mark each with `"source": "drafted-for-demo"`.
   - Add **at least 9 more QPs across trades** so mapping has real competition, with fewer PCs each:
     - Other welding QPs, e.g. Construction Welder, Stud Welding Operator, Senior Welder – Pipes & Plates
     - Fitter Fabrication
     - Electrician (domestic)
     - Plumber
     - Sewing Machine Operator
     - Assistant Beauty Therapist
     - Two-wheeler Service Technician
     - Mason
2. **Trade-vernacular lexicon** (`data/lexicon/lexicon.json`):
   - At least 150 entries.
   - Hindi (Devanagari), Hinglish and English slang → canonical NSQF terms and process codes.
   - Includes tools, processes, defects and safety items.
   - Has an endpoint for assessor-confirmed additions, so the lexicon grows.
3. **Synthetic data generator** (`scripts/generate_synthetic.py`, seeded and reproducible):
   - 60 worker profiles with narratives in Hindi, Hinglish and English, each with a ground-truth QP.
   - Synthetic weld evidence images drawn procedurally with Pillow/OpenCV: plates, bead lines, with good / porosity / undercut / spatter / incomplete variants, and ground-truth labels.
   - Everything is written to `data/synthetic/` and labelled synthetic.

- Commits: `feat(data): NQR welding QP and multi-trade QP corpus` → `feat(data): trade-vernacular lexicon` → `feat(data): reproducible synthetic workers and weld evidence generator`

### Phase 4 — M1 + M2 mapping engine (backend)

1. Text normalisation: Devanagari/Hinglish handling, lowercase, lexicon expansion.
2. Hybrid scorer:
   - BM25 over QP + NOS + PC text.
   - Embedding cosine re-rank (lazy-loaded model, BM25 fallback).
   - Calibrated confidence via softmax over the top-k.
3. Endpoints:
   - `POST /declarations`: stores the narrative, language and consent.
   - `POST /declarations/{id}/map`: returns top-3 QPs, confidence, matched lexicon terms (explainability), and a per-PC claim prefill.
4. `ml/eval_mapping.py`: reports top-1 / top-3 accuracy on the synthetic narratives (target ≥ 85% top-3; report honestly whatever you get).
5. Export a compact **QP pack** (QPs + BM25 stats + lexicon) for the device: `GET /packs/latest`.

- Commits: `feat(mapping): hybrid BM25 + embedding QP mapping engine` → `test(mapping): evaluation script and accuracy report`

### Phase 5 — Frontend foundation

1. Vite + Vue 3 + TS + Tailwind + Router + Pinia + vue-i18n (English + Hindi) + `vite-plugin-pwa` + Dexie.
2. Login page with demo-account chips, then role-based home: Worker, Assessor, QA dashboard.
3. Visual direction:
   - Clean, high-contrast, mobile-first, saffron/green/navy accents.
   - Large touch targets; works at a 360 px width.
   - A persistent **online/offline indicator** and an **outbox counter**.
4. API client with JWT. Show a "Synthetic demo data" badge in the footer.

- Commit: `feat(frontend): Vue 3 PWA shell with auth, i18n and offline indicator`

### Phase 6 — Worker app: M1 declaration (offline-capable)

1. Consent screen (DPDP-style, plain language, Hindi + English).
2. "Kaam ki Kahani" screen:
   - A big mic button with live transcript (Web Speech API).
   - Typed fallback.
   - Icon cards for trades / tools / processes for low-literacy users.
   - Language toggle.
3. **Mapper-lite in TypeScript** (BM25 + lexicon over the cached QP pack) gives an instant provisional QP **while offline**. When online, the server's result replaces it.
4. Results: top-3 QPs with confidence bars and matched terms; the worker confirms, which creates an assessment request.
5. Everything is stored in Dexie first, then queued in the outbox.

- Commits: `feat(worker): voice-first declaration with consent` → `feat(offline): on-device mapper-lite and outbox sync`

### Phase 7 — M3 evidence plan + assessor checklist

1. Rules engine (backend + mirrored in TS): `PC → evidence route`. Critical and safety PCs are locked to `observe`. Show a lock icon and explain why.
2. Assessor app:
   - Assessment queue.
   - Open a candidate to see the PC checklist grouped by NOS, the evidence route per PC, and **rubric anchors** (level descriptors + example images from synthetic good/poor welds).

- Commit: `feat(assessor): PC-level evidence plan and guided checklist`

### Phase 8 — M4 signed capture + integrity

1. Capture flow on the assessor device (camera via `getUserMedia`, with file-upload fallback for laptops):
   - Three shots: Process → Product → Person, with on-screen guidance.
   - The **one-time challenge code** is generated per assessment and must be shown on the "Person" shot.
2. On-device QC in TypeScript, with instant feedback ("Too blurry — hold steady"):
   - Blur via Laplacian variance on a downscaled canvas.
   - Brightness check.
   - Basic framing check.
3. Capture packet = `{image, sha256, gps (if permitted), timestamp, device_id, challenge_code, assessment_id}`.
   - Signed with **WebCrypto ECDSA P-256** using a non-extractable key generated once per device (public key registered with the server).
   - Image is AES-GCM-encrypted in the Dexie vault, then placed in the outbox.
4. Server integrity service:
   - Verify the signature and the hash.
   - Compute the **pHash** and compare against all stored evidence (Hamming distance threshold).
   - Check EXIF / timestamp / GPS plausibility.
   - Optionally OCR the challenge code (pytesseract if installed, otherwise skip with a note).
   - Produces `integrity_flags`.
5. Demo proof: re-uploading the same or a slightly edited photo for another candidate must be **flagged as reused**. Write a test for it.

- Commits: `feat(capture): guided P-P-P capture with on-device quality checks` → `feat(security): device-signed evidence packets with encrypted vault` → `feat(integrity): signature verification and pHash reuse detection`

### Phase 9 — M5 blind-first AI shadow rater

1. Demo vision model (`ml/train_shadow_rater.py`):
   - Trained on the synthetic weld images.
   - Classical features: bead continuity, edge irregularity, spot/porosity count via OpenCV, texture stats.
   - scikit-learn classifier (RandomForest/GBM) → per-PC suggestion (0–3 level) + confidence.
   - Saved to `ml/models/`.
   - Behind a `ShadowRater` interface so a ViT/ONNX model can be swapped in later. Document this.
   - Label it in the UI as "Demo model trained on synthetic images".
2. Scoring API:
   - `POST /assessments/{id}/scores` (assessor's blind score per PC).
   - `GET /assessments/{id}/ai-suggestions` returns suggestions **only for PCs already scored by this assessor** (403 / omit otherwise). Write tests that prove the AI can't be seen first.
3. UI: after the assessor scores a PC, reveal the AI suggestion with a fade-in, gap highlight and explanation. If |gap| ≥ threshold, require a **reason code**:
   - evidence unclear
   - AI misread image
   - observed live differently
   - rubric ambiguity
   - other + note

   The assessor may revise the score; the original blind score is kept in the audit ledger.

- Commits: `feat(ml): demo shadow-rater model on synthetic weld evidence` → `feat(scoring): blind-first scoring with server-enforced AI reveal and reason codes`

### Phase 10 — M6 calibration, competency profile, sign-off, credential

1. **Golden packets:** 10 pre-graded synthetic evidence packets with consensus scores, randomly seeded into assessor queues (not marked as golden to the assessor).
2. **Calibration engine:**
   - Krippendorff's α (ordinal) per PC and on the final decision.
   - Per-assessor **Calibration Index** (agreement with golden consensus + drift over time).
   - QA dashboard (ECharts): α trend, assessor × NOS drift heat-map, centre comparison, reason-code breakdown.
   - The individual index is visible only to that assessor and QA.
3. **Competency profiler:**
   - Per-PC → per-NOS aggregate using the QP's theory/practical/viva weights.
   - 70% pass rule → **Full / Partial / Gap** with per-NOS explanations and suggested bridge modules.
4. **Sign-off:**
   - The assessor reviews the profile and signs off (re-enters their password).
   - The system **never** auto-submits; this is enforced server-side.
5. **Credential:**
   - On sign-off, issue a **W3C Verifiable Credential JSON** signed with a server Ed25519 key.
   - A PDF competency profile (reportlab) with a QR code linking to a public `/verify/{credential_id}` page that checks the signature and shows status.
   - A `GET /export/sidh/{assessment_id}` endpoint returning a SIDH-style JSON payload (mock schema, documented as such).

- Commits: `feat(calibration): golden packets, Krippendorff alpha and calibration index` → `feat(dashboard): QA calibration dashboard with drift heat-maps` → `feat(profile): NSQF competency profile with Full/Partial/Gap recommendation` → `feat(credential): assessor sign-off, signed verifiable credential and QR verification`

### Phase 11 — Consistency study (the PS's "evidence of consistency improvement")

1. `scripts/simulate_study.py` runs a **crossover AB/BA simulation**:
   - 30 packets × 8 simulated raters with realistic bias/noise.
   - Unassisted vs assisted (assisted = rubric anchors + blind-first AI reveal with partial adjustment).
   - Computes α per PC and on the decision, decision flips, and time proxy.
   - Writes `docs/results/consistency_study.md` + PNG charts.
   - **Clearly labelled SIMULATED.**
2. **Real study mode in the app:**
   - QA creates a study, real people (e.g. teammates / ITI instructors) score the same packets with assistance OFF then ON.
   - The dashboard computes α live from real scores.

- Commit: `feat(study): crossover consistency study (simulation + live study mode)`

### Phase 12 — Offline hardening + sync

1. Service worker caches:
   - App shell.
   - The QP pack.
   - Lexicon.
   - Golden packets.
   - Rubric images.
2. Outbox sync:
   - Triggered on the `online` event plus Background Sync where supported.
   - Exponential backoff, chunked upload for images, idempotency keys.
   - Server deduplicates by packet hash.
3. Sync-down endpoint for updated packs.
4. A Playwright test that goes **offline**, completes a declaration + capture, goes online, and asserts the server received signed packets.

- Commit: `feat(offline): resilient outbox sync, sync-down packs and offline e2e test`

### Phase 13 — Full mode (Docker)

1. `docker-compose.yml`:
   - `postgres` (pgvector image)
   - `minio`
   - `redis`
   - `backend`
   - `worker` (Celery for vision + mapping jobs)
   - `frontend` (nginx serving the built PWA)
2. Storage and queue adapters switch by env; pgvector stores QP embeddings.
3. `make full-up`, `make lite-up`. Test lite mode still works.

- Commit: `feat(infra): docker compose full mode with Postgres+pgvector, MinIO and Celery`
4. **If I don't install Docker, skip this phase's runtime test** but still commit the compose file and docs. Instead, add and commit `feat(db): MySQL / SQL Server support via setup_db script`, tested against the SQL server I have installed.

### Phase 14 — Quality, CI, docs, demo (milestone)

1. CI (`.github/workflows/ci.yml`): ruff + pytest (backend), eslint + vitest + build (frontend), Playwright smoke (golden path).
2. `scripts/seed_demo.py` builds one command → a fully populated demo:
   - Workers with declarations.
   - Assessments in different states.
   - Golden packets.
   - A signed credential.
3. `scripts/screenshots.ts` (Playwright) auto-captures the **4 screenshots for our SIH PPT** into `docs/screenshots/` at 1280×800 and a mobile 390×844 variant:
   1. Worker voice declaration (Hindi)
   2. QP match + per-PC claim prefill
   3. Guided P-P-P capture + challenge code
   4. Assessor blind scoring & calibration dashboard
4. `README.md` must have:
   - Pitch line.
   - Problem → solution mapping table (PS requirement → module → where in code).
   - Mermaid architecture.
   - Quick start (lite mode, 3 commands), full mode.
   - Demo accounts.
   - **5-minute demo script** for judges.
   - Support-vs-replace table.
   - Results (mapping accuracy + consistency study, labelled simulated/real).
   - Licences.
   - Team credits.
5. `docs/DEMO_SCRIPT.md`, `docs/API.md` (link to FastAPI `/docs`), `docs/PRIVACY.md` (DPDP notes).
6. Tag `v1.0.0` and create a GitHub release with the screenshots attached (`gh release create`).

- Commits: `ci: lint, unit and e2e pipelines` → `feat(demo): one-command demo seed and screenshot automation` → `docs: README, demo script, architecture and results`

### Milestone tags

| Tag | Reached after |
|---|---|
| `v0.1.0` | Phase 2 |
| `v0.3.0` | Phase 4 |
| `v0.5.0` | Phase 8 |
| `v0.8.0` | Phase 10 |
| `v1.0.0` | Phase 14 |

Push tags with `git push --tags`.

---

## 7. The golden-path demo (must work end-to-end before v1.0.0)

1. Log in as **worker1**.
2. Give consent.
3. Speak in Hindi: *"Main 6 saal se fabrication shop mein kaam karta hoon, CO2 aur argon dono welding karta hoon, plate aur pipe joint banata hoon, grinding karke finishing deta hoon"*.
4. See Welding QP as #1 with confidence and matched terms.
5. Confirm.
6. Switch to **assessor1**.
7. Open the assessment and see the PC checklist with locked critical PCs.
8. Do the P-P-P capture with the challenge code — **with the network turned off**.
9. Score PCs blind; the AI reveals after each.
10. One big gap forces a reason code.
11. Go back online; the outbox syncs.
12. Try uploading a reused photo for worker2 → it is **flagged**.
13. Review the competency profile (Partial: e.g. a GTAW gap → bridge module).
14. Sign off.
15. A credential is issued.
16. Scan the QR → the verify page shows a valid signature.
17. Log in as **qa1** → see the calibration dashboard, α, drift heat-map and the audit-chain "verified" badge.

---

## 8. Definition of done

- [ ] A new public GitHub repo with **≥ 25 meaningful commits pushed sequentially**, milestone tags, and a v1.0.0 release.
- [ ] `make lite-up` (or the documented npm/py commands) runs the whole app locally without Docker; the golden path works.
- [ ] All six modules M1–M6 work, offline capture + sync works, and blind-first is enforced server-side.
- [ ] Backend tests + frontend unit tests + the Playwright golden path pass in CI.
- [ ] Mapping accuracy report and consistency study report are in `docs/results/` (honestly labelled).
- [ ] The 4 PPT screenshots are in `docs/screenshots/`.
- [ ] README with the demo script, architecture, support-vs-replace table and licences.

When finished, give me:

- The repo URL.
- The commit log (`git log --oneline`).
- How to run the demo.
- Any shortcuts or limitations to mention honestly to the judges.

---

## Session clarifications (given by the user during the build)

- **System installs approved:** Node.js LTS and GitHub CLI via winget.
- **Public GitHub repo approved:** `Aribhussain/skillsync-copilot`; push after every commit.
- **Embeddings approved:** CPU torch + sentence-transformers + the MiniLM model (~700 MB, project-level).
- **Playwright:** never download Playwright's Chromium locally. Use the installed Brave via `PLAYWRIGHT_BROWSER_PATH` (with a fresh temp profile, never the personal profile), `channel: undefined`, path in `.env.example`, `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`. CI keeps `npx playwright install chromium`.
- **No hallucinated code:** verify APIs against installed versions, run everything, label unverified data, report honestly.
- **Stopping / checkpoints:** when asked to stop, finish or commit (as `wip:` if green) the current chunk, update the CLAUDE.md "Progress / Resume here" section, commit and push, stop dev servers, and wait.
