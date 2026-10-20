# Architecture

SkillSync Co-Pilot has five layers. The field device is offline-first. All AI services sit behind interfaces, so a better model can be swapped in without touching the workflow.

```mermaid
flowchart TB
  subgraph L1["L1 · Field device (PWA, offline-first)"]
    W["Worker app<br/>voice / typed / icon cards"]
    A["Assessor app<br/>checklist · capture · blind scoring"]
    ML["mapper-lite<br/>BM25 + lexicon (TS)"]
    QC["capture QC<br/>blur · brightness · framing"]
    SG["capture signer<br/>SHA-256 + ECDSA P-256"]
    V[("encrypted IndexedDB vault<br/>+ outbox (Dexie, AES-GCM)")]
    W --> ML
    A --> QC --> SG --> V
    W --> V
  end

  subgraph L2["L2 · Sync & gateway (FastAPI)"]
    GW["REST API · JWT / RBAC"]
    SV["signature verify"]
    CL["consent ledger"]
    TR["task runner<br/>BackgroundTasks | Celery"]
  end

  subgraph L3["L3 · AI & scoring services (Python)"]
    S1["1 · QP mapping<br/>BM25 + lexicon + embeddings"]
    S2["2 · evidence plan<br/>rules engine"]
    S3["3 · evidence integrity<br/>pHash · EXIF · time · GPS"]
    S4["4 · AI shadow rater<br/>(blind-first gate)"]
    S5["5 · calibration<br/>Krippendorff α"]
    S6["6 · competency profiler"]
  end

  subgraph L4["L4 · Data & audit"]
    DB[("SQLite (default) | MySQL | SQL Server<br/>| Postgres+pgvector (Docker)")]
    FS[("local storage/ | S3 store (SeaweedFS)")]
    AL[("hash-chained audit ledger")]
    VI["VectorIndex<br/>numpy cosine | pgvector"]
  end

  subgraph L5["L5 · Human gate & outputs"]
    SO["assessor sign-off<br/>(password re-entry)"]
    VC["W3C Verifiable Credential<br/>+ QR verify page"]
    SX["SIDH-style export API"]
    DQ["QA calibration dashboard"]
  end

  V -- "outbox → REST (idempotent)" --> GW
  GW -- "sync-down packs<br/>QPs · lexicon · golden packets" --> V
  GW --> SV --> S3
  GW --> CL
  GW --> TR
  TR --> S1 & S3 & S4
  GW --> S1 & S2 & S4 & S5 & S6
  S1 --> VI
  S1 & S2 & S3 & S4 & S5 & S6 --> DB
  S3 --> FS
  GW --> AL
  S6 --> SO --> VC
  SO --> SX
  S5 --> DQ
```

## Key flows

1. **Declaration (M1/M2).** The worker gives consent, then tells their "kaam ki kahani". Mapper-lite produces a provisional QP on the device. Once online, the server's hybrid mapper replaces it. The worker confirms, and that creates an assessment request.
2. **Evidence plan (M3).** The rules engine (Python, mirrored in TS) assigns a route to every PC. Critical and safety PCs are always `observe`.
3. **Capture (M4).** The assessor captures Process, Product and Person shots. The Person shot shows the one-time challenge code. Each packet is QC-checked, hashed, ECDSA-signed and stored in the encrypted vault, then sent through the outbox. The server verifies the signature and hash, then checks pHash reuse and EXIF/time/GPS plausibility.
4. **Blind-first scoring (M5).** The assessor scores a PC, and only then does `GET /assessments/{id}/ai-suggestions` return the suggestion for that PC. A gap at or above the threshold requires a reason code.
5. **Profile and sign-off (M6).** PC scores roll up into NOS scores using the QP's theory/practical/viva weights and the 70% rule, giving a Full / Partial / Gap recommendation. The assessor signs off by re-entering their password. Only then is an Ed25519-signed VC issued, with a PDF and a QR code.
6. **Calibration.** Golden packets sit in assessor queues without being marked. Krippendorff's α and the Calibration Index are computed from them, and QA sees drift heat-maps.

## Database strategy

The data layer is database-agnostic through SQLModel/SQLAlchemy and Alembic, and `DATABASE_URL` picks the backend. Models use only portable types: SQLAlchemy `JSON`, `String(n)` for indexed text, and no ARRAY/JSONB. Embeddings are stored as JSON and loaded into an in-memory numpy matrix behind a `VectorIndex` interface. pgvector is used only in Docker full mode.
