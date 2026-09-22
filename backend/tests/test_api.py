from fastapi.testclient import TestClient

from app.main import app


def test_health_and_run_workflow():
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    scenario = client.post("/api/scenarios", json={"name": "Brake test", "scenario_type": "emergency_braking"})
    assert scenario.status_code == 201
    algorithm = client.post("/api/algorithms", json={"name": "Cautious", "version": "cautious-v2"})
    assert algorithm.status_code == 201
    run = client.post(f"/api/runs/{scenario.json()['id']}/{algorithm.json()['id']}")
    assert run.status_code == 201
    assert "minimum_time_to_collision_s" in run.json()["metrics"]