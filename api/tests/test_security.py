from fastapi.testclient import TestClient

from app.main import app
from app.security import create_access_token

client = TestClient(app)


def test_data_endpoint_requires_token():
    response = client.get("/api/kpis")
    assert response.status_code == 401


def test_invalid_token_is_rejected():
    response = client.get("/api/kpis", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_viewer_cannot_trigger_admin_backfill():
    token = create_access_token("viewer@sismowatch.local", "viewer")
    response = client.post(
        "/api/admin/backfill",
        json={"days": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_viewer_cannot_read_ai_audit():
    token = create_access_token("viewer@sismowatch.local", "viewer")
    response = client.get(
        "/api/admin/ai-runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
