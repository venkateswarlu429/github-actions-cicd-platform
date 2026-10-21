"""Tests for the sample consumer service."""

from fastapi.testclient import TestClient

from app.main import SERVICE_NAME, app

client = TestClient(app)


def test_root_reports_identity() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == SERVICE_NAME
    assert "version" in body


def test_healthz_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_greet_uses_name() -> None:
    response = client.get("/greet/devops")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, devops!"}


def test_greet_strips_whitespace() -> None:
    response = client.get("/greet/%20sre%20")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, sre!"}


def test_unknown_route_is_404() -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
