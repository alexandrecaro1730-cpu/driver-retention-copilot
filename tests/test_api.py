from app.api import create_app
from fastapi.testclient import TestClient


def test_health_endpoint(settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "x-request-id" in response.headers


def test_chat_endpoint(settings) -> None:
    client = TestClient(create_app(settings))
    response = client.post(
        "/v1/chat",
        json={
            "driver_id": "D-LON-001",
            "message": "Maria waited 135 minutes for a 1.5km airport trip.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["critic"]["decision"] == "APPROVE"
    assert payload["plan"]["total_gbp_value"] == 25


def test_chat_endpoint_rejects_unknown_driver_safely(settings) -> None:
    client = TestClient(create_app(settings))
    response = client.post(
        "/v1/chat",
        json={"driver_id": "D-LON-999", "message": "Airport issue"},
    )
    assert response.status_code == 422
    assert "not found" in response.json()["detail"]


def test_chat_endpoint_validates_message_length(settings) -> None:
    client = TestClient(create_app(settings))
    response = client.post("/v1/chat", json={"driver_id": "D-LON-001", "message": ""})
    assert response.status_code == 422
