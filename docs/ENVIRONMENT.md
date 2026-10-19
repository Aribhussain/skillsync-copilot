# Development environment (Phase 0 report)

Captured on 2026-10-19 on the primary development machine.

| Component | Version / status |
|---|---|
| OS | Windows 11 Home Single Language 10.0.26300 |
| Shells | Windows PowerShell 5.1, Git Bash |
| Git | 2.55.0.windows.3 (user: Arib Hussain) |
| GitHub CLI | 2.102.0 (installed via winget) |
| Node.js / npm | 24.20.0 LTS / 11.19.0 (installed via winget) |
| Python | 3.11.9 via `py -3.11` (3.10.11 is also present but not used) |
| Docker / Compose | 29.8.0 / v5.5.1, engine running (full mode only) |
| Database | SQLite (bundled with Python, default) · MySQL Community Server 8.0.46, service `MySQL80` running · SQL Server not installed · PostgreSQL not installed (Docker only) |
| Browser for e2e | Brave (per-user install), driven by Playwright through `PLAYWRIGHT_BROWSER_PATH` |
| Package manager | winget v1.29 |

## VS Code extensions

Already installed: `ms-python.python`, `ms-python.vscode-pylance`, `dbaeumer.vscode-eslint`, `esbenp.prettier-vscode`, `bradlc.vscode-tailwindcss`, `eamodio.gitlens`.

Installed during setup: `Vue.volar`, `charliermarsh.ruff`, `ms-azuretools.vscode-docker`, `ms-playwright.playwright`, `humao.rest-client`, `mtxr.sqltools`, `mtxr.sqltools-driver-sqlite`, `yzhang.markdown-all-in-one`, `bierner.markdown-mermaid`.
