"""Executable release gates for the direct MATLAB solver architecture."""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from mcp.matlab_mcp import MatlabMcpWorker
from topoptpilot.benchmarks.equivalence import run_equivalence_gate
from topoptpilot.tools import ALLOWED_TOOLS

ROOT = Path(__file__).resolve().parents[1]


def run_audit(include_online: bool = True) -> dict:
    report = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "version": "6.2.1", "gates": {}}
    report["gates"].update(_source_gates())
    report["gates"].update(_matlab_gates())
    report["online_agent"] = ({"pass": None, "reason": "run DeepSeek V4 Flash benchmark campaign separately"}
                               if include_online else {"pass": None, "skipped": True})
    report["offline_release_ready"] = all(gate["pass"] for gate in report["gates"].values())
    report["release_ready"] = report["offline_release_ready"] and report["online_agent"]["pass"] is True
    return report


def _source_gates() -> dict[str, dict]:
    desktop = ROOT / "desktop/src-tauri/target/release/topoptpilot-desktop.exe"
    installer = ROOT / "desktop/src-tauri/target/release/bundle/nsis/TopOptPilot_6.2.1_x64-setup.exe"
    read = lambda path: (ROOT / path).read_text(encoding="utf-8")
    models, service = read("topoptpilot/schemas/models.py"), read("topoptpilot/service/research_service.py")
    subagents, canvas = read("topoptpilot/agent_runtime/subagents.py"), read("desktop/src/ExperimentCanvas.tsx")
    setup, store = read("desktop/src/ResearchSetup.tsx"), read("topoptpilot/memory/research_state.py")
    api, reports = read("topoptpilot/api/fastapi_app.py"), read("topoptpilot/reports/generator.py")
    obsolete = ("UPGRADE_FIDELITY", "FidelityManager", "EXPERIMENT_PLANNER", "EXPERIMENT_EXECUTOR", "REPORT_WRITER")
    return {
        "desktop_app": {"pass": desktop.exists() and installer.exists(), "executable": str(desktop), "installer": str(installer)},
        "direct_solver_schema": {"pass": all(v in models for v in ("solver_profile", "estimated_seconds", "estimated_memory_mb", "execution_mode")) and not any(v in models for v in obsolete)},
        "isolated_agent_roles": {"pass": all(v in subagents for v in ("GUIDE", "SCIENTIST", "INDEPENDENT_REVIEWER")) and not any(v in subagents for v in obsolete)},
        "direct_matlab_only": {"pass": all(marker in service for marker in (
            "MatlabMcpWorker", 'backend != "MATLAB_MCP"', 'strict_matlab": True',
            '"python_fallback": False')) and not any(marker in service for marker in (
                "PythonFEMWorker(", "MatlabBackend(", "Matlab3DAdapter("))},
        "guided_setup": {"pass": "previewGuide" in setup and "AI_SUGGESTED" in setup and "time_seconds" in setup and "f0" not in setup.lower()},
        "research_canvas": {"pass": all(v in canvas for v in ("HYPOTHESIS", "PLAN", "RUN", "ANALYZE", "COMPARE", "DECIDE", "REPORT"))},
        "agent_provenance": {"pass": all(v in store for v in ("decision_source", "intent_source", "policy_version", "evidence_ids_json"))},
        "websocket_realtime": {"pass": "stream-ticket" in api and "_ws_tickets.pop" in api},
        "fact_grounded_reports": {"pass": "未计算" in reports and "evaluation" in reports and "artifact" in reports.lower()},
        "credential_not_in_sqlite": {"pass": "api_key" not in store.lower() and "/api/settings/agent-key" in api},
        "tool_whitelist": {"pass": all(tool in read(".pi/extensions/topopt-tools.ts") for tool in ALLOWED_TOOLS)},
    }


def _matlab_gates() -> dict[str, dict]:
    gates: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="topoptpilot_direct_gate_") as directory:
        worker = MatlabMcpWorker(directory, ROOT)
        try:
            for dimension, grid in ((2, [12, 4]), (3, [4, 2, 2])):
                grid_key = "grid2d" if dimension == 2 else "grid3d"
                task = {"task_id": f"audit-{dimension}d", "fidelity": "DIRECT", "dimension": dimension,
                        "mesh_level": "direct", "solver_profile": {"grid": grid, "accuracy": "standard",
                        "variant": "optimized_cpu", "acceleration_mode": "vectorized_cpu", "max_iterations": 2},
                        "load_case": "cantilever", "projection": "heaviside_projection",
                        "params": {"volfrac": .4, "penal": 3, "rmin": 1.5, "max_iter": 2, grid_key: grid}}
                key = f"matlab_mcp_{dimension}d"
                try:
                    result = worker.run(task, "AUDIT", f"E{dimension}D")
                    solver = result["solver"]
                    gates[key] = {"pass": solver.get("backend") == key,
                                  "matlab_version": solver.get("matlab_version"), "mcp_version": solver.get("mcp_version"),
                                  "solver_entry_sha256": solver.get("solver_entry_sha256")}
                except Exception as exc:
                    gates[key] = {"pass": False, "error": str(exc)[:500]}
            try:
                gates["matlab_equivalence"] = run_equivalence_gate(worker, dimension=2)
            except Exception as exc:
                gates["matlab_equivalence"] = {"pass": False, "error": str(exc)[:500]}
        finally:
            worker.close()
    return gates


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TopOptPilot direct-solver release gates")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    report = run_audit(include_online=not args.offline)
    (ROOT / "release_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"offline_release_ready": report["offline_release_ready"], "release_ready": report["release_ready"]}, ensure_ascii=False, indent=2))
    return 0 if (report["offline_release_ready"] if args.offline else report["release_ready"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
