"""Recoverable migration of existing state into a read-only Legacy Workspace."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .research_state import ResearchStateStore


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def migrate_to_workspace_state(store: ResearchStateStore, data_dir: Path) -> dict:
    """Map unmapped historical Research without deleting any evidence.

    A snapshot manifest is written before the first mutation.  If any mutation
    fails, the database copy is restored and the error is raised.
    """
    unmapped = [item for item in store.list_research() + store.list_research(archived=True)
                if not item.get("workspace_id")]
    if not unmapped:
        return {"migrated": 0, "backup": None}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = data_dir / ".migration-backups" / ("workspace-" + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    copied: list[dict] = []
    # The SQLite source of truth is mandatory.  Artifact folders are copied as
    # available, never guessed or rewritten.
    targets = [store.db_path] + [data_dir / item["id"] for item in unmapped]
    try:
        for source in targets:
            if not source.exists():
                continue
            destination = backup / source.name
            if source.is_dir():
                shutil.copytree(source, destination)
                for file in destination.rglob("*"):
                    if file.is_file():
                        copied.append({"path": str(file.relative_to(backup)), "sha256": _digest(file)})
            else:
                shutil.copy2(source, destination)
                copied.append({"path": destination.name, "sha256": _digest(destination)})
        (backup / "manifest.json").write_text(json.dumps({"version": 1, "files": copied}, indent=2),
                                               encoding="utf-8")
        legacy = next((item for item in store.list_workspaces() if item["project_id"] == "legacy-unbound"), None)
        if not legacy:
            legacy = store.create_workspace({"id": "WS-LEGACY", "project_id": "legacy-unbound",
                                             "name": "Legacy Workspace", "read_only": True})
        for research in unmapped:
            store.update_research(research["id"], workspace_id=legacy["id"])
        return {"migrated": len(unmapped), "backup": str(backup)}
    except Exception:
        db_copy = backup / store.db_path.name
        if db_copy.exists():
            shutil.copy2(db_copy, store.db_path)
        raise
