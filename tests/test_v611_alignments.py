"""Desktop API, warmup-stat, and MATLAB-equivalence contract tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import topoptpilot.api.fastapi_app as api_app
from mcp.matlab_mcp import MatlabMcpWorker
from topoptpilot.benchmarks.equivalence import run_equivalence_gate
from topoptpilot.service import ResearchService


def _routes() -> set[str]:
    return {f"{sorted(r.methods)[0]} {r.path}"
            for r in api_app.app.routes
            if hasattr(r, "methods") and "api" in getattr(r, "path", "")}


def test_documented_credential_alias_routes_exist():
    routes = _routes()
    assert "PUT /api/settings/agent-credential" in routes
    assert "DELETE /api/settings/agent-credential" in routes
    # Legacy names stay for compatibility.
    assert "POST /api/settings/agent-key" in routes


def test_documented_guide_parse_route_exists():
    routes = _routes()
    assert "POST /api/research/guide/parse" in routes
    assert "POST /api/guide" in routes


def test_backend_version_is_620():
    service = ResearchService(tempfile.mkdtemp(), max_workers=1)
    health = service.health()
    assert health["version"] == "6.2.1"


def test_worker_health_exposes_warmup_and_run_stats():
    with tempfile.TemporaryDirectory() as directory:
        worker = MatlabMcpWorker(directory)
        health = worker.health()
        assert "startup_ms" in health
        assert "warmup" in health
        assert "last_runs" in health
        worker.close()


def test_equivalence_module_imports_and_returns_contract():
    # Pure contract test without launching MATLAB: the gate must accept any
    # object exposing run(); the real MATLAB run is exercised by release_audit.
    class FakeWorker:
        def run(self, task, research_id, experiment_id):
            value = {"compliance": 1.0, "iterations": 3}
            variant = task.get("solver_variant", "optimized_cpu")
            density = [1.0, 0.0] if variant == "reference_cpu" else [1.0, 0.0]
            return {
                "objective": {"compliance": value["compliance"]},
                "constraints": {"volume_fraction": 0.4},
                "quality": {"gray_ratio": 0.01, "connected_components": 1},
                "solver": {"solver_variant": variant,
                           "iterations": value["iterations"],
                           "matlab_version": "24.1 (R2024a)"},
                "artifacts": {"density": density},
            }

    result = run_equivalence_gate(FakeWorker(), dimension=2)
    assert result["pass"] is True
    assert result["relative_error_reference_vs_optimized"] == 0.0
    assert result["density_identical_across_labels"] is True
    assert result["iterations_match"] is True
