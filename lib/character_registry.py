"""Reusable character registry for the Persona fork (M3).

A separable JSON store — stdlib only, no OpenMontage imports — so the
consistent-character engine can be lifted onto another core untouched.

Characters are keyed by a stable character id, NOT by project: a trained LoRA
adapter, the reference photos, and the identity notes belong to the character
and are reused across every project that casts them.

Layout (default root: $PERSONA_CHARACTERS_DIR or <repo>/characters — gitignored):

    characters/
      <char-id>/
        character.json      # identity record (see schema below)
        refs/               # canonical reference images (local copies)

character.json:
    {
      "id": "ana",
      "name": "Ana",
      "description": "auburn curly hair, green eyes, beauty mark ...",
      "created_at": "...", "updated_at": "...",
      "reference_images": ["refs/portrait.png", ...],   # relative to char dir
      "loras": [
        {"provider": "fal", "model_family": "flux",
         "adapter_url": "https://...", "trigger_phrase": "anak woman",
         "trained_at": "...", "training_task_id": "...", "steps": 2500}
      ],
      "notes": ""
    }

Safety properties: every entry point validates char_id (single chokepoint in
_char_dir — no path traversal); corrupt records surface as CharacterNotFound
with the offending path (tools convert that to a clean ToolResult); writes are
atomic with a unique temp file per writer plus a best-effort per-character
flock, so concurrent writers cannot corrupt a record. Remote adapter/result
URLs may expire — reference images are always copied local; adapter URLs
record provenance and can be re-trained from the refs if a provider drops the
file.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")


def default_root() -> Path:
    env = os.environ.get("PERSONA_CHARACTERS_DIR")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent.parent / "characters"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CharacterNotFound(KeyError):
    """Unknown, invalid, or unreadable character record."""


class CharacterRegistry:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root else default_root()

    # ---- paths (char_id validated here — the single chokepoint) ----

    def _char_dir(self, char_id: str) -> Path:
        if not isinstance(char_id, str) or not _ID_RE.fullmatch(char_id):
            raise CharacterNotFound(
                f"Invalid character id {char_id!r} — use kebab-case: [a-z0-9-], max 64 chars"
            )
        return self.root / char_id

    def _record_path(self, char_id: str) -> Path:
        return self._char_dir(char_id) / "character.json"

    # ---- io ----

    def _read(self, char_id: str) -> dict[str, Any]:
        path = self._record_path(char_id)
        if not path.is_file():
            known = ", ".join(c.get("id", "?") for c in self.list()) or "none"
            raise CharacterNotFound(
                f"Unknown character '{char_id}' (looked in {self.root}). Known: {known}"
            )
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CharacterNotFound(f"Character record corrupt at {path}: {exc}") from exc
        if not isinstance(record, dict) or record.get("id") != char_id:
            raise CharacterNotFound(
                f"Character record at {path} does not belong to '{char_id}' "
                f"(id field: {record.get('id') if isinstance(record, dict) else type(record).__name__!s}). "
                f"If the directory was copied, fix the 'id' field to match."
            )
        return record

    def _write(self, char_id: str, record: dict[str, Any]) -> None:
        record["id"] = char_id  # the directory name is authoritative
        record["updated_at"] = _now()
        path = self._record_path(char_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Unique temp per writer: two concurrent writers must never share a
        # temp path (one replace would install the other's bytes, the second
        # replace would crash).
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(record, fh, indent=2, ensure_ascii=False)
            os.replace(tmp_name, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    @contextlib.contextmanager
    def _locked(self, char_id: str) -> Iterator[None]:
        """Best-effort exclusive lock for read-modify-write (POSIX flock;
        no-op on Windows, where the unique temp still prevents corruption)."""
        char_dir = self._char_dir(char_id)
        char_dir.mkdir(parents=True, exist_ok=True)
        with open(char_dir / ".lock", "w") as fh:
            try:
                import fcntl

                fcntl.flock(fh, fcntl.LOCK_EX)
            except ImportError:  # pragma: no cover - Windows
                pass
            yield

    # ---- API ----

    def create(
        self, char_id: str, *, name: Optional[str] = None, description: str = ""
    ) -> dict[str, Any]:
        if self._record_path(char_id).is_file():
            raise ValueError(f"Character '{char_id}' already exists")
        record = {
            "id": char_id,
            "name": name or char_id,
            "description": description,
            "created_at": _now(),
            "updated_at": _now(),
            "reference_images": [],
            "loras": [],
            "notes": "",
        }
        with self._locked(char_id):
            self._write(char_id, record)
        return record

    def get(self, char_id: str) -> dict[str, Any]:
        return self._read(char_id)

    def exists(self, char_id: str) -> bool:
        try:
            return self._record_path(char_id).is_file()
        except CharacterNotFound:
            return False

    def list(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        out = []
        for record_path in sorted(self.root.glob("*/character.json")):
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue  # a corrupt character must not hide the others from list()
            if isinstance(record, dict) and record.get("id"):
                out.append(record)
        return out

    def add_reference(self, char_id: str, image_path: str | Path) -> Path:
        """Copy a reference image into the character's refs/ and record it."""
        src = Path(image_path)
        if not src.is_file():
            raise FileNotFoundError(f"Reference image not found: {src}")
        with self._locked(char_id):
            record = self._read(char_id)
            refs_dir = self._char_dir(char_id) / "refs"
            refs_dir.mkdir(parents=True, exist_ok=True)
            src_bytes = src.read_bytes()
            dest = refs_dir / src.name
            counter = 1
            while dest.exists() and dest.read_bytes() != src_bytes:
                dest = refs_dir / f"{src.stem}-{counter}{src.suffix}"
                counter += 1
            # Skip the copy when identical bytes are already in place — including
            # re-adding a path that IS the registered refs/ file (SameFileError).
            if not dest.exists():
                shutil.copy2(src, dest)
            rel = str(dest.relative_to(self._char_dir(char_id)))
            refs = record.setdefault("reference_images", [])
            if rel not in refs:
                refs.append(rel)
                self._write(char_id, record)
        return dest

    def reference_paths(self, char_id: str) -> list[Path]:
        """Existing reference files. Compare with missing_reference_paths() —
        a silent shrink here degrades identity quality downstream."""
        record = self._read(char_id)
        char_dir = self._char_dir(char_id)
        return [
            char_dir / rel
            for rel in record.get("reference_images", [])
            if (char_dir / rel).is_file()
        ]

    def missing_reference_paths(self, char_id: str) -> list[str]:
        """Registered refs whose files are gone — callers should surface these."""
        record = self._read(char_id)
        char_dir = self._char_dir(char_id)
        return [
            rel
            for rel in record.get("reference_images", [])
            if not (char_dir / rel).is_file()
        ]

    def add_lora(self, char_id: str, adapter: dict[str, Any]) -> dict[str, Any]:
        """Record a trained adapter, keyed to the character (reuse-everywhere)."""
        if not isinstance(adapter, dict) or not adapter.get("adapter_url"):
            raise ValueError("adapter record requires a non-empty 'adapter_url'")
        entry = {"trained_at": _now(), **adapter}
        with self._locked(char_id):
            record = self._read(char_id)
            record.setdefault("loras", []).append(entry)
            self._write(char_id, record)
        return entry

    def latest_lora(
        self, char_id: str, *, model_family: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        record = self._read(char_id)
        loras = [
            l for l in record.get("loras", [])
            if model_family is None or l.get("model_family") == model_family
        ]
        return loras[-1] if loras else None
