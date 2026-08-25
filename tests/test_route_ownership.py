from __future__ import annotations

from collections import Counter

from idesktop_v2.api.app import app


def test_fastapi_has_no_duplicate_method_path_pairs() -> None:
    pairs = [
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", None) or ())
        if method not in {"HEAD", "OPTIONS"}
    ]
    assert [pair for pair, count in Counter(pairs).items() if count > 1] == []


def test_compare_and_pareto_have_one_authoritative_owner() -> None:
    paths = [route.path for route in app.routes]
    assert paths.count("/api/research/{research_id}/compare") == 1
    assert paths.count("/api/research/{research_id}/pareto") == 1
    assert paths.count("/api/research/from-engineering-run/{run_id}") == 1
