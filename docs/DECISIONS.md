# Decisions log

Each entry: date · decision · why.

## 2026-10-19 · Environment

- **OS:** Windows 11. Node.js 24 LTS and GitHub CLI were installed with winget, with approval. Python 3.11.9 is used through the `py -3.11` launcher. The default `python` on PATH is 3.10, which is too old.
- **Database:** PostgreSQL is not installed natively, by design. SQLite is the default. The machine has **MySQL 8.0.46** (service `MySQL80`); SQL Server is not installed. MySQL is the "real server" target for `scripts/setup_db.py`.
- **Docker:** Docker 29.8 is installed and running, but it is used only for Phase 13 full mode. Lite mode never needs it.
- **Playwright:** browsers are **not downloaded locally**. Playwright drives the installed **Brave** browser through `PLAYWRIGHT_BROWSER_PATH` with a fresh temp profile. Brave is installed per-user at `%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe`, not under Program Files. The config tries the env var first, then the Program Files path, then the per-user path. `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` is set. CI uses `npx playwright install chromium` on GitHub's runners.
- **Location:** the repo lives under a OneDrive-synced Desktop. `node_modules/`, `.venv/` and `storage/` are git-ignored. If OneDrive sync causes file locks, pause sync during installs.
