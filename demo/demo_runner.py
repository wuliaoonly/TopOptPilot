"""Read-only V6.3 demonstration preflight.

This command validates recorded evidence and prints the desktop demonstration
timeline.  It never runs FEM, calls an online model, or synthesizes a success
result.  A passing preflight means that the evidence package is present; it is
not a substitute for the live Tauri/MATLAB demonstration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "6.3.0"
EXPECTED_INSTALLER_SHA256 = "E0EF7591D48CCCC2F6BE025EE52BF4E6730AE38DE74646707279A39859B33CC0"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TIMELINE = (
    ("0:00–0:40", "启动 Tauri App 与授权 Workspace"),
    ("0:40–1:30", "展示 Quick/Deep 共用工作台"),
    ("1:30–2:30", "提交真实 Quick MATLAB 2D 小网格运行"),
    ("2:30–3:20", "检查迭代、制品、哈希与 solver provenance"),
    ("3:20–4:00", "Quick → Deep 不可变晋升"),
    ("4:00–5:10", "ExperimentDraft、预算和人工审批"),
    ("5:10–6:10", "Evaluator 分轴状态与受控对比"),
    ("6:10–7:15", "Final Reviewer REVISE / APPROVE 双路径"),
    ("7:15–8:00", "报告门禁与复现证据"),
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def collect_preflight() -> dict[str, Any]:
    audit_path = ROOT / "release_audit.json"
    campaign_path = ROOT / "docs/validation/2026-08-25-v6.3-online-campaign.md"
    contracts_path = ROOT / "topoptpilot/tools/contracts.py"
    installer_path = (
        ROOT / "desktop/src-tauri/target/release/bundle/nsis/"
        "TopOptPilot_6.3.0_x64-setup.exe"
    )

    checks: list[dict[str, Any]] = []

    try:
        audit = _load_json(audit_path)
        checks.extend((
            {"id": "audit_version", "required": True,
             "pass": audit.get("version") == EXPECTED_VERSION,
             "detail": f"recorded={audit.get('version')} expected={EXPECTED_VERSION}"},
            {"id": "offline_release_ready", "required": True,
             "pass": audit.get("offline_release_ready") is True,
             "detail": str(audit.get("offline_release_ready"))},
            {"id": "online_agent", "required": True,
             "pass": (audit.get("online_agent") or {}).get("pass") is True,
             "detail": str((audit.get("online_agent") or {}).get("pass"))},
            {"id": "reviewer_gate", "required": True,
             "pass": (audit.get("online_agent") or {}).get("reviewer_gate_verified") is True,
             "detail": str((audit.get("online_agent") or {}).get("reviewer_gate_verified"))},
        ))
    except ValueError as exc:
        checks.append({"id": "release_audit", "required": True, "pass": False, "detail": str(exc)})

    checks.extend((
        {"id": "campaign_record", "required": True, "pass": campaign_path.is_file(),
         "detail": campaign_path.relative_to(ROOT).as_posix()},
        {"id": "tool_contract", "required": True, "pass": contracts_path.is_file(),
         "detail": contracts_path.relative_to(ROOT).as_posix()},
    ))

    if installer_path.is_file():
        actual = _sha256(installer_path)
        checks.append({"id": "installer_sha256", "required": False,
                       "pass": actual == EXPECTED_INSTALLER_SHA256,
                       "detail": actual})
    else:
        checks.append({"id": "installer_sha256", "required": False, "pass": None,
                       "detail": "installer not present in this checkout"})

    required_pass = all(item["pass"] is True for item in checks if item["required"])
    return {"version": EXPECTED_VERSION, "requiredPass": required_pass, "checks": checks}


def print_preflight(report: dict[str, Any]) -> None:
    print(f"TopOptPilot V{report['version']} demo evidence preflight")
    for item in report["checks"]:
        status = "PASS" if item["pass"] is True else "WARN" if item["pass"] is None else "FAIL"
        scope = "required" if item["required"] else "optional"
        print(f"[{status:4}] {item['id']:<24} {scope:<8} {item['detail']}")
    print("PREFLIGHT=" + ("PASS" if report["requiredPass"] else "FAIL"))


def print_timeline() -> None:
    print("TopOptPilot V6.3 desktop demonstration timeline")
    for period, action in TIMELINE:
        print(f"{period}  {action}")
    print("\nAll live metrics must come from the current run or an explicitly dated evidence record.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate V6.3 demo evidence without running FEM or an Agent")
    parser.add_argument("--check", action="store_true", help="print the evidence preflight")
    parser.add_argument("--timeline", action="store_true", help="print the eight-minute desktop timeline")
    parser.add_argument("--json", action="store_true", help="emit the evidence preflight as JSON")
    args = parser.parse_args()

    report = collect_preflight()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if args.check or not args.timeline:
            print_preflight(report)
        if args.timeline:
            print_timeline()
    return 0 if report["requiredPass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
