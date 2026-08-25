from __future__ import annotations

from pathlib import Path

from topoptpilot import release_audit


def test_artifact_gate_uses_generated_canonical_tool_contract() -> None:
    result = release_audit._artifact_gate()
    assert result["pass"] is True
    assert result["tools"] == 16
    assert Path(result["generated"]).as_posix().endswith(".pi/generated/topopt-tools.ts")


def test_source_gates_cover_direct_solver_and_shared_stream_tickets() -> None:
    gates = release_audit._source_gates()
    assert gates["direct_solver_schema"]["pass"] is True
    assert gates["direct_matlab_only"]["pass"] is True
    assert gates["websocket_realtime"]["pass"] is True
    assert gates["tool_whitelist"]["pass"] is True
    assert gates["engineering_solver_manifest"]["pass"] is True
    assert gates["engineering_solver_manifest"]["files"] > 0


def test_desktop_gate_reports_v622_standard_package(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(release_audit, "ROOT", tmp_path)
    release = tmp_path / "desktop/src-tauri/target/release"
    (release / "topoptpilot-desktop.exe").parent.mkdir(parents=True)
    (release / "topoptpilot-desktop.exe").write_bytes(b"exe")
    installer = release / "bundle/nsis/TopOptPilot_6.2.2_x64-setup.exe"
    installer.parent.mkdir(parents=True)
    installer.write_bytes(b"installer")
    resources = release / "resources"
    for relative in (
        "bin/topoptpilot-backend.exe",
        "node/node.exe",
        "vendor/matlab-mcp-server/matlab-mcp-server-windows-x64.exe",
        "mcp/matlab_mcp/topopt-tools.json",
        "求解器模块/2D/TopOpt_integrated/TopOpt_integrated/topopt_main.m",
        "求解器模块/TopOpt-3D/TopOpt-3D/topopt3d_main.m",
        "matlab/engineering/run_topopt_job.m",
        "matlab/engineering/TopOpt_2D/topopt_main.m",
        "matlab/engineering/TopOpt-3D/topopt3d_main.m",
        "matlab/engineering/solver-sources.json",
    ):
        path = resources / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"resource")

    result = release_audit._desktop_gate()
    assert result["pass"] is True
    assert result["package_kind"] == "standard-local-matlab"
    assert result["runtime_optional"] is True
    assert result["runtime_in_standard_package"] is False


def test_desktop_gate_rejects_runtime_inside_standard_package(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(release_audit, "ROOT", tmp_path)
    runtime = tmp_path / "desktop/src-tauri/target/release/resources/runtime"
    runtime.mkdir(parents=True)
    result = release_audit._desktop_gate()
    assert result["pass"] is False
    assert result["runtime_in_standard_package"] is True
