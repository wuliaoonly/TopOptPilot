"""Deterministic direct MATLAB solver profiles and total research budgets."""

from __future__ import annotations

class DirectSolverPolicy:
    @staticmethod
    def dimension(research: dict) -> int:
        value = str((research.get("geometry") or {}).get("dimension", "2D")).upper()
        return 3 if value in {"3", "3D"} else 2

    @classmethod
    def profile(cls, research: dict, *, verify: bool = False) -> dict:
        dimension = cls.dimension(research)
        grid = ([36, 12, 8] if verify else [24, 8, 6]) if dimension == 3 else (
            [144, 48] if verify else [96, 32])
        cells = 1
        for value in grid:
            cells *= value
        return {
            "grid": grid,
            # The authoritative 3D MATLAB entry accepts only these stable
            # protocol values.  "high" represents a verification profile;
            # verification remains a grid/profile choice, not a fidelity tier.
            "accuracy": "high" if verify else "standard",
            "variant": "optimized_cpu",
            "acceleration_mode": "vectorized_cpu",
            "max_iterations": 160 if verify else 100,
            "estimated_seconds": round(max(2.0, cells * (0.0018 if dimension == 3 else 0.0007)), 1),
            "estimated_memory_mb": round(max(64.0, cells * (0.045 if dimension == 3 else 0.012)), 1),
        }

    @staticmethod
    def budget(research: dict, experiments: list[dict]) -> dict:
        configured = research.get("budgets") or {}
        total = int(configured.get("total", research.get("budget_total", 12)))
        used = sum(1 for item in experiments if item.get("run_id"))
        time_limit = configured.get("time_seconds")
        time_remaining = None
        if time_limit is not None:
            used_seconds = sum(float(((item.get("result") or {}).get("solver") or {}).get(
                "solve_time_seconds") or item.get("elapsed_seconds") or 0) for item in experiments)
            time_remaining = max(0.0, float(time_limit) - used_seconds)
        return {
            "limits": {"total": total}, "used": {"total": used},
            "remaining": {"total": max(0, total - used)},
            "time_remaining": time_remaining,
        }
