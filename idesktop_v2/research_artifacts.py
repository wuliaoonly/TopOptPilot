"""Adapt TopOptPilot experiment outputs to the shared artifact viewer contract."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from idesktop_v2.engineering.artifact_index import media_type_for


def _file_ref(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    root = root.resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"artifact path is outside research data root: {resolved}") from exc
    if not resolved.is_file():
        raise ValueError(f"artifact file does not exist: {resolved}")
    return {
        "relativePath": relative,
        "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        "mediaType": "application/octet-stream",
        "sizeBytes": resolved.stat().st_size,
    }


def build_research_artifact_index(research: dict[str, Any], data_root: Path) -> dict[str, Any]:
    root = Path(data_root).resolve()
    experiments: list[dict[str, Any]] = []
    for experiment in research.get("experiments", []):
        result = experiment.get("result") or {}
        artifacts = result.get("artifacts") or {}
        refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in artifacts.values():
            if not isinstance(raw, str) or not raw:
                continue
            path = Path(raw)
            if path.exists():
                ref = _file_ref(path, root)
                if ref["relativePath"] not in seen:
                    refs.append(ref)
                    seen.add(ref["relativePath"])
        experiments.append({
            "experimentId": experiment.get("id", ""),
            "status": experiment.get("status", ""),
            "dimension": experiment.get("dimension", 2),
            "solverProfile": experiment.get("solver_profile", {}),
            "legacyFidelity": experiment.get("legacy_fidelity"),
            "backend": experiment.get("backend", ""),
            "provenance": {"ownerType": "research-experiment", "backend": experiment.get("backend", "unknown")},
            "files": refs,
            "metrics": {
                "compliance": (result.get("objective") or {}).get("compliance"),
                "grayRatio": (result.get("quality") or {}).get("gray_ratio"),
            },
        })
    return {"researchId": research.get("id", ""), "experiments": experiments}


def create_source_snapshot(record, data_root: Path) -> dict[str, Any]:
    """Copy a completed quick run into an immutable, hash-addressed baseline."""
    root = Path(data_root).resolve() / "source-snapshots"
    root.mkdir(parents=True, exist_ok=True)
    snapshot_id = f"SNAP-{uuid.uuid4().hex[:12].upper()}"
    temporary = root / f".{snapshot_id}.tmp"
    destination = root / snapshot_id
    temporary.mkdir(parents=False, exist_ok=False)
    refs: list[dict[str, Any]] = []
    source_refs: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    try:
        for ref in [*record.files, *record.snapshots]:
            source = (record.run_dir / Path(*Path(ref.relative_path).parts)).resolve()
            if record.run_dir.resolve() not in source.parents or not source.is_file():
                raise ValueError("quick run contains an invalid artifact path")
            target = temporary / Path(*Path(ref.relative_path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            value = target.read_bytes()
            sha256 = hashlib.sha256(value).hexdigest()
            if sha256.lower() != ref.sha256.lower():
                raise ValueError(f"quick run artifact digest changed: {ref.relative_path}")
            digest.update(ref.relative_path.encode("utf-8")); digest.update(value)
            item = {"relativePath": ref.relative_path, "sha256": sha256,
                    "mediaType": media_type_for(target), "sizeBytes": len(value)}
            refs.append(item)
            if target.suffix.lower() in {".m", ".json"} or ref.relative_path.startswith("source/"):
                source_refs.append(item)
        manifest = {
            "snapshotId": snapshot_id,
            "sourceDigest": digest.hexdigest(),
            "configDigest": record.config_digest,
            "environment": {"lane": record.lane.value},
            "sourceFiles": source_refs,
            "artifacts": refs,
            "provenance": dict(record.provenance),
            "originRunId": record.run_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        (temporary / "snapshot.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, destination)
        for path in destination.rglob("*"):
            if path.is_file():
                path.chmod(0o444)
        return manifest
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
