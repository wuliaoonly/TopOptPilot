---
name: solver-profile-budgeting
description: Reviews direct MATLAB grid, time, memory, and experiment-count budgets before a proposal is submitted.
allowed-tools: research_get_context research_get_budget solver_get_capabilities policy_compile_intent experiment_preview
---

# Direct Solver Profile Budgeting

Use the Research Contract dimension and verified machine capabilities. Prefer the smallest grid
capable of answering the current scientific question. The Policy owns numerical grid selection.
Reject proposals that exceed total experiment, compute-time, memory, or iteration limits. A final
verification uses `VERIFY_CANDIDATE`; it is not a distinct fidelity level. In COPILOT mode the
proposal waits for confirmation. In AUTONOMOUS mode it may run only after Policy, Safety, and
Budget pass. Every formal solve uses MATLAB MCP and failures never fall back to Python.
