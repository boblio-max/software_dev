import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app, SessionLocal, Base, engine
import seed as seed_module


def _seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_module.seed(db)
    finally:
        db.close()


def _register(client, username="tester"):
    res = client.post("/api/v1/auth/register", params={
        "email": f"{username}@example.com",
        "username": username,
        "password": "password123",
    })
    assert res.status_code in (200, 400)
    login = client.post("/api/v1/auth/login", data={"username": username, "password": "password123"})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_health():
    client = TestClient(app)
    assert client.get("/health").status_code == 200


def test_auth_flow():
    client = TestClient(app)
    token = _register(client, "authuser")
    assert client.get("/api/v1/analytics/progress", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/api/v1/analytics/progress").status_code == 401


def test_skills_unlocked():
    client = TestClient(app)
    token = _register(client, "skilluser")
    res = client.get("/api/v1/skills/unlocked", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_submit_and_hint_flow():
    _seed()
    client = TestClient(app)
    token = _register(client, "submituser")
    # task 1 seeded
    res = client.post(
        "/api/v1/tasks/submit",
        params={"task_id": 1, "code": "print('Hello, World!')", "struggle_time_seconds": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["passed"] is True
    hint = client.get(
        f"/api/v1/hints/next?submission_id={data['submission_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert hint.status_code == 200
    assert "content" in hint.json()