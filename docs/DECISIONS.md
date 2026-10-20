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

## 2026-10-20 · Blind-first scoring, calibration, profile and credential (Phases 9–10)

- **Shadow rater:** two RandomForests over 11 explainable OpenCV features, behind a `ShadowRater` interface. On synthetic data it scores 95% defect / 90% level accuracy on the hold-out and on a fresh seed. It's labelled everywhere as a demo trained on synthetic images, and the model file is a git-ignored build artefact that the server trains on first use.
- **Blind-first lives in the API, not the UI.** The suggestion is computed and returned only in the response to the assessor's own blind score, and `GET /ai-suggestions` returns 403 for unscored PCs. Tests assert that no assessor-visible endpoint contains AI fields beforehand.
- **Krippendorff's α is in-house and verified:** it matches the GPL reference implementation to < 1e-15 on 300 random matrices and on the canonical example. The reference ran only in a scratch venv and is not a dependency. With few raters and low consensus variance, α is sensitive: one lenient assessor (+1) drove ordinal α to about 0.1–0.35 in tests. That is the intended behaviour.
- **Golden packets are SYNTHETIC.** Their consensus is derived from generator ground truth. They're seeded as ordinary-looking assessments whose evidence is genuinely signed by a per-assessor "demo seeder" device key.
- **Audit ledger changed to "append, then seal"** after a real race under concurrent requests (`UNIQUE constraint failed: audit_ledger.seq`). Entries are written atomically with the business change (DB-assigned `seq`) and chained after commit by a serialised in-process sealer (`chain_index`, `prev_hash`, `hash`). Existing ledgers keep their hashes (`chain_index = seq`). Limitations: there's a millisecond-scale unsealed window, and a multi-process deployment would need a DB-level lock for the sealer (e.g. `SELECT … FOR UPDATE` on MySQL/Postgres).
- **Competency profile:** each PC carries its own theory/practical/viva marks from the NQR file, and level fractions are 0 / 0.4 / 0.8 / 1.0. Full requires a ≥ 70% aggregate, every PC assessed and no critical PC below level 2. That's why the golden-path case (71.1% aggregate with a GTAW gap) comes out **Partial**.
- **Sign-off is the only path to a decision.** It needs the assessor's re-entered password, every PC scored, every large-gap reason filled, and a justification if the decision differs from the recommendation. A Gap decision issues no credential.
- **Verifiable credential:**
  - The issuer is a `did:key` derived from a server Ed25519 key in `storage/keys/` (git-ignored).
  - The proof follows the `eddsa-jcs-2022` construction. Canonicalisation is sorted-key compact JSON, which equals JCS for this document's value types (numbers are serialised as strings to avoid float-format differences).
  - **Not yet checked with an external VC verifier.** base58btc is checked against the standard "Hello World!" vector, and the DID has the expected `z6Mk` prefix.
- **SIDH export is a mock schema** (`skillsync.sidh-export.mock.v1`, `"mock": true`), not the official Skill India Digital Hub API.
- **Frontend notes:**
  - vue-echarts fills its parent, so charts sit in fixed-height wrappers.
  - Vite now pre-bundles echarts and qrcode, because runtime discovery made the dev server re-optimise mid-navigation and hang the first dashboard load.
