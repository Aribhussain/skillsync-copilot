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

## 2026-10-20 · Evidence capture and integrity (Phase 8)

- **Capture QC thresholds are measured, not guessed.** On a ≤320 px grayscale copy, the Laplacian variance of sharp synthetic welds is 15–37 and blurred ones are below 2.5, so the blur threshold is 8. Real phone photos score higher, so the thresholds need field calibration.
- **Framing check is basic by design.** It measures the share of edge energy in the central 60% box, with magnitudes clipped at the 95th percentile (so printed text or glare can't dominate) and the median subtracted as a noise floor. A first version failed our own captioned samples: the crisp caption text dominated the edge energy. Known limitation: a small off-centre subject on a *noisy* background isn't detected.
- **Signatures:** the device key is ECDSA P-256, generated non-extractable in WebCrypto. The packet is a canonical `|`-joined string, identical in TypeScript and Python and checked by a literal test on both sides. WebCrypto's raw r‖s signature is converted to DER for `cryptography`. GPS is rounded to 6 decimals *before* signing, because JS `toFixed` and Python `.6f` can differ on exact ties. The e2e test has Brave sign and the Python server verify.
- **Vault:** images are AES-GCM-256 encrypted with a non-extractable key, and the ciphertext is wiped after a successful sync.
- **pHash reuse threshold is 6, not 10.** Measured on 300 synthetic welds:
  - Different images: min 0, 1st percentile 6, median 28; 4.5% of pairs are ≤ 10 and about 1% are ≤ 6, because the synthetic welds share one template.
  - Brightness ±15%, contrast, JPEG quality 60 and 50% resizing all move pHash by ≤ 4.
  - A 5% crop moves it up to 32, and a 3° rotation up to 16, so those are not caught.
  - dHash in combination was *less* edit-robust (brightness alone moves it by 12).
  - ORB + RANSAC verification did not separate the classes on these low-texture images: different welds reached 59 inliers while true crops dropped to 8. It was therefore not shipped.

  Exact copies (same SHA-256 in another assessment) are always flagged. All integrity results are **flags for assessor review; nothing is auto-rejected**. A guard test keeps the 12 bundled demo samples pairwise above the threshold (the closest pair is 8).
- **OCR of the challenge code is optional.** pytesseract isn't installed, so a `ocr_skipped` info flag tells the assessor to confirm the code visually.
- **Process note:** piping test output through `tail` hides failures, so checks now use `set -o pipefail` / `PIPESTATUS`. A repo-root `ruff.toml` makes `scripts/` and `ml/` lint the same way from any directory.
