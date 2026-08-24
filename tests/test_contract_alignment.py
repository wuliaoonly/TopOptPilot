from __future__ import annotations

from scripts.generate_contracts import outputs
from topoptpilot.tools.contracts import ALLOWED_TOOLS, TOOL_CONTRACTS


def test_generated_contract_files_are_current() -> None:
    for path, expected in outputs().items():
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8") == expected, path


def test_canonical_agent_allowlist_contains_exactly_sixteen_tools() -> None:
    assert len(ALLOWED_TOOLS) == 16
    assert ALLOWED_TOOLS == frozenset(TOOL_CONTRACTS)
    assert "experiment_submit" in ALLOWED_TOOLS
    assert not ({"terminal", "terminal_command", "engineering_patch"} & ALLOWED_TOOLS)
