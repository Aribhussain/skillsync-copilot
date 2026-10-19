# Decisions log

Each entry: date · decision · why.

## 2026-10-19 · Environment

- **OS:** Windows 11. Node.js 24 LTS and GitHub CLI were installed with winget, with approval. Python 3.11.9 is used through the `py -3.11` launcher. The default `python` on PATH is 3.10, which is too old.
- **Database:** PostgreSQL is not installed natively, by design. SQLite is the default. The machine has **MySQL 8.0.46** (service `MySQL80`); SQL Server is not installed. MySQL is the "real server" target for `scripts/setup_db.py`.
- **Docker:** Docker 29.8 is installed and running, but it is used only for Phase 13 full mode. Lite mode never needs it.
- **Playwright:** browsers are **not downloaded locally**. Playwright drives the installed **Brave** browser through `PLAYWRIGHT_BROWSER_PATH` with a fresh temp profile. Brave is installed per-user at `%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe`, not under Program Files. The config tries the env var first, then the Program Files path, then the per-user path. `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` is set. CI uses `npx playwright install chromium` on GitHub's runners.
- **Location:** the repo lives under a OneDrive-synced Desktop. `node_modules/`, `.venv/` and `storage/` are git-ignored. If OneDrive sync causes file locks, pause sync during installs.

## 2026-10-19 · Backend core

- **Krippendorff's α is implemented in-house.** The `krippendorff` PyPI package is GPL-3.0-or-later, which conflicts with our MIT/Apache/BSD-only rule. We implement the coincidence-matrix formulation (nominal / ordinal / interval) in numpy and test it against published reference values.
- **Passwords use `bcrypt` directly instead of passlib.** passlib is unmaintained and warns with bcrypt ≥ 4. JWTs use **PyJWT** (MIT).
- **Audit timestamps are stored as ISO strings** inside the hash chain, so the hash recomputes identically on SQLite, MySQL and SQL Server, whatever their datetime precision.
- **Datetimes are timezone-aware UTC.** SQLModel's `UTCDateTime` stores UTC portably.

## 2026-10-19 · Mapping engine (Phase 4)

- **Embeddings installed, with approval:** CPU-only torch 2.14.1 and sentence-transformers 6.1.0. The model `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) is cached in `storage/models/hf`. It loads in a background thread, and until it's ready the mapper runs BM25 + lexicon and says so (`embedding_note`). CI and tests run BM25-only, plus a fake embedder for the hybrid code path.
- **Why the lexicon matters:** the multilingual model scores cosine("argon ka kaam", "GTAW TIG welding") at only 0.16, because it doesn't know shop-floor slang. On the held-out hard set the lexicon adds +13.3 points of top-3 accuracy.
- **Confidence temperature is T = 0.12, set before evaluation.** Fitting on the template-generated calibration split gives T = 0.03 (over-confident), because that split is almost perfectly separable. Real calibration needs real narratives.
- **`no_match` flag:** when nothing in the narrative matches the corpus, the mapper reports 0 confidence instead of an arbitrary ranking.
- **Claim prefill is gated by distinctive NOS keywords.** A first version claimed 48 of 48 PCs from generic words such as "weld" and "plate".
- **Process note:** the `v0.3.0` tag was pushed on a commit where `ml/eval_mapping.py` still had ruff E501 (line-length) findings, because a shell heredoc broke the command chain that should have stopped on lint failure. The very next commit fixes them. The tag was not moved, to avoid rewriting published history.
