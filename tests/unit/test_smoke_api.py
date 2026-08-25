"""API tests for smoke dashboard endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from querymind.api.app import create_app
from querymind.api import smoke_routes


def test_dashboard_page_served() -> None:
    client = TestClient(create_app())
    res = client.get("/")
    assert res.status_code == 200
    assert "QueryMind" in res.text
    assert "/api/smoke/parse" in res.text


def test_parse_endpoint_masks_secrets() -> None:
    client = TestClient(create_app())
    res = client.post(
        "/api/smoke/parse",
        json={
            "curl": (
                "curl -H 'Authorization: Bearer secret-token-xyz' "
                "https://example.com/api/health"
            )
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["preview"]["method"] == "GET"
    assert "secret-token-xyz" not in str(data)


def test_run_requires_destructive_confirm(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(smoke_routes, "reports_root", lambda: tmp_path)
    client = TestClient(create_app())
    curl = "curl -X POST https://example.com/api/users -d '{\"a\":1}'"
    res = client.post("/api/smoke/run", json={"curl": curl, "confirm_destructive": False})
    assert res.status_code == 409
    assert res.json()["detail"]["destructive"] is True


def test_smoke_api_health() -> None:
    client = TestClient(create_app())
    res = client.get("/api/smoke/health")
    assert res.status_code == 200
    assert res.json()["module"] == "ApiSmokeTesting"
