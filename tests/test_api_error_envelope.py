from __future__ import annotations

from fastapi.testclient import TestClient

from idesktop_v2.api.app import app


def test_http_errors_use_structured_public_envelope() -> None:
    response = TestClient(app).get("/api/research/DOES-NOT-EXIST")
    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "HTTP_404"
    assert payload["source"] == "API"
    assert payload["retryable"] is False
    assert isinstance(payload["detail"], dict)


def test_validation_errors_use_stable_machine_code() -> None:
    response = TestClient(app).post(
        "/api/research/from-engineering-run/missing",
        json={"budgetTotal": 0},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "REQUEST_VALIDATION_FAILED"
    assert isinstance(payload["detail"]["errors"], list)
