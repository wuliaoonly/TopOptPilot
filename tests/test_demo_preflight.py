from __future__ import annotations

import json
from pathlib import Path

from demo.demo_runner import EXPECTED_VERSION, collect_preflight
from idesktop_v2.engineering.runs import RunCreateRequest
from topoptpilot.schemas.api_contracts import ExperimentDraft


def test_v63_demo_preflight_requires_recorded_release_evidence() -> None:
    report = collect_preflight()
    assert report["version"] == EXPECTED_VERSION == "6.3.0"
    assert report["requiredPass"] is True
    required = {item["id"]: item for item in report["checks"] if item["required"]}
    assert required["offline_release_ready"]["pass"] is True
    assert required["online_agent"]["pass"] is True
    assert required["reviewer_gate"]["pass"] is True


def test_demo_preflight_does_not_treat_missing_installer_as_fabricated_success() -> None:
    report = collect_preflight()
    installer = next(item for item in report["checks"] if item["id"] == "installer_sha256")
    assert installer["pass"] in {True, None}


def test_demo_sample_inputs_match_current_quick_and_deep_contracts() -> None:
    samples = Path("demo/sample_inputs")
    quick = RunCreateRequest.model_validate(
        json.loads((samples / "mbb_2d_quick.json").read_text(encoding="utf-8"))
    )
    deep = ExperimentDraft.model_validate(
        json.loads((samples / "mbb_2d_deep_draft.json").read_text(encoding="utf-8"))
    )

    assert quick.task["dimension"] == "2d"
    assert quick.task["geometry"]["nelz"] == 1
    assert deep.backend == "MATLAB_MCP"
    assert deep.dimension == 2
