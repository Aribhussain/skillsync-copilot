"""Resumable chunked uploads for evidence images over flaky rural connections.

  init     POST /uploads {sha256, size, total_chunks} -> upload_id (idempotent per user +
           sha256, so a retry after a dropped connection resumes the same upload)
  chunk    PUT  /uploads/{id}/chunks/{n}  raw bytes (idempotent; re-sending is harmless)
  status   GET  /uploads/{id}             which chunks the server already has
  finish   POST /assessments/{id}/evidence with upload_id instead of a file; the server
           reassembles, checks size + SHA-256, then runs the normal signature verification.
Chunks live under storage/uploads/<id>/ and are deleted after assembly.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from fastapi import HTTPException

CHUNK_SIZE = 256 * 1024
MAX_CHUNKS = 40  # 10 MB


class UploadStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _dir(self, upload_id: str) -> Path:
        if not upload_id.isalnum() or len(upload_id) > 64:
            raise HTTPException(404, "Unknown upload")
        return self.root / upload_id

    def _meta(self, upload_id: str) -> dict:
        p = self._dir(upload_id) / "meta.json"
        if not p.exists():
            raise HTTPException(404, "Unknown upload")
        return json.loads(p.read_text(encoding="utf-8"))

    def init(self, user_id: int, sha256: str, size: int, total_chunks: int) -> dict:
        if total_chunks < 1 or total_chunks > MAX_CHUNKS or size > MAX_CHUNKS * CHUNK_SIZE:
            raise HTTPException(413, "Upload too large")
        upload_id = hashlib.sha256(f"{user_id}:{sha256}:{size}".encode()).hexdigest()[:32]
        d = self._dir(upload_id)
        d.mkdir(parents=True, exist_ok=True)
        meta_path = d / "meta.json"
        if not meta_path.exists():
            meta = {"user_id": user_id, "sha256": sha256, "size": size, "total_chunks": total_chunks}
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
        return self.status(upload_id, user_id)

    def status(self, upload_id: str, user_id: int) -> dict:
        meta = self._meta(upload_id)
        if meta["user_id"] != user_id:
            raise HTTPException(403, "Not your upload")
        received = sorted(int(p.stem) for p in self._dir(upload_id).glob("*.part"))
        return {
            "upload_id": upload_id,
            "chunk_size": CHUNK_SIZE,
            "total_chunks": meta["total_chunks"],
            "received": received,
            "complete": len(received) == meta["total_chunks"],
        }

    def put_chunk(self, upload_id: str, user_id: int, index: int, data: bytes) -> dict:
        meta = self._meta(upload_id)
        if meta["user_id"] != user_id:
            raise HTTPException(403, "Not your upload")
        if not 0 <= index < meta["total_chunks"] or len(data) > CHUNK_SIZE:
            raise HTTPException(422, "Bad chunk index or size")
        (self._dir(upload_id) / f"{index}.part").write_bytes(data)
        return self.status(upload_id, user_id)

    def assemble(self, upload_id: str, user_id: int) -> bytes:
        st = self.status(upload_id, user_id)
        if not st["complete"]:
            missing = sorted(set(range(st["total_chunks"])) - set(st["received"]))
            raise HTTPException(409, f"Upload incomplete; missing chunks {missing[:10]}")
        meta = self._meta(upload_id)
        d = self._dir(upload_id)
        data = b"".join((d / f"{i}.part").read_bytes() for i in range(meta["total_chunks"]))
        if len(data) != meta["size"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            shutil.rmtree(d, ignore_errors=True)  # drop corrupt chunks so a retry starts clean
            raise HTTPException(400, "Reassembled upload does not match its size / SHA-256")
        shutil.rmtree(d, ignore_errors=True)
        return data
