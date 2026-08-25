from __future__ import annotations

from pathlib import Path


def test_readme_describes_v63_desktop_credential_and_solver_boundaries() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "DASHSCOPE_API_KEY" in readme
    assert "只提供 Windows Tauri 桌面应用" in readme
    assert "Quick 本机 MATLAB" in readme
    assert "Deep 通过 MATLAB MCP" in readme
    assert "F0/F1=Python 2D" not in readme
    assert "F2=Python 3D" not in readme
    assert "F3=MATLAB MCP" not in readme
