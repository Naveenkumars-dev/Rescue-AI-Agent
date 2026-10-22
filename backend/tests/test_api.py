"""API endpoint tests via FastAPI TestClient."""

from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "mode" in r.json()


def test_info(client):
    r = client.get("/api/info")
    assert r.status_code == 200
    j = r.json()
    assert j["agent_name"].startswith("RescueFlow")
    assert "kit_credit" in j


def test_list_incidents(client):
    r = client.get("/api/incidents")
    assert r.status_code == 200
    assert len(r.json()) >= 5
    inc = r.json()[0]
    assert "preliminary_score" in inc


def test_get_incident_404(client):
    assert client.get("/api/incidents/INC-999").status_code == 404


def test_create_incident_validation(client):
    # missing required field -> 422
    r = client.post("/api/incidents", json={"type": "fire"})
    assert r.status_code == 422
    # valid
    r = client.post("/api/incidents", json={
        "type": "chemical spill", "location": "Industrial Park Rd", "report": "Chemical spill reported.",
        "severity": 4, "time_sensitivity": 4, "affected_people_num": 5, "hazard_level": 4,
        "hazards": "fumes",
    })
    assert r.status_code == 201
    assert r.json()["id"].startswith("INC-")
    assert r.json()["type"] == "chemical spill"


def test_evaluate_decision(client):
    r = client.post("/api/decisions/evaluate", json={"incident_id": "INC-001"})
    assert r.status_code == 200
    j = r.json()
    assert j["decision"]["incident_id"] == "INC-001"
    assert j["decision_id"].startswith("DEC-")
    assert "tool_calls" in j and len(j["tool_calls"]) >= 6


def test_evaluate_decision_404(client):
    assert client.post("/api/decisions/evaluate", json={"incident_id": "INC-999"}).status_code == 404


def test_get_and_list_decisions(client):
    client.post("/api/decisions/evaluate", json={"incident_id": "INC-001"})
    all_d = client.get("/api/decisions")
    assert all_d.status_code == 200
    assert len(all_d.json()) >= 1
    did = all_d.json()[0]["decision_id"]
    one = client.get(f"/api/decisions/{did}")
    assert one.status_code == 200
    assert one.json()["decision_id"] == did
    assert client.get("/api/decisions/DEC-9999").status_code == 404


def test_approve_and_reject(client):
    client.post("/api/decisions/evaluate", json={"incident_id": "INC-002"})
    did = client.get("/api/decisions").json()[0]["decision_id"]
    r = client.post(f"/api/decisions/{did}/approve", json={"reviewer_note": "ok"})
    assert r.status_code == 200
    assert r.json()["decision_status"] == "APPROVED"
    client.post("/api/decisions/evaluate", json={"incident_id": "INC-003"})
    dec003 = client.get("/api/decisions?incident_id=INC-003").json()
    did2 = dec003[0]["decision_id"]
    r2 = client.post(f"/api/decisions/{did2}/reject", json={"reviewer_note": "no"})
    assert r2.status_code == 200
    assert r2.json()["decision_status"] == "REJECTED"


def test_arena_evaluate(client):
    r = client.post("/api/arena/evaluate", json={"incident_ids": ["INC-001", "INC-002", "INC-003"]})
    assert r.status_code == 200
    j = r.json()
    assert len(j["ranking"]) == 3
    assert j["ranking"][0]["incident_id"] == "INC-001"
    assert "explanation" in j


def test_arena_min_two_incidents(client):
    r = client.post("/api/arena/evaluate", json={"incident_ids": ["INC-001"]})
    assert r.status_code == 422  # min_length=2


def test_arena_reassess(client):
    r = client.post("/api/arena/reassess", json={
        "incident_ids": ["INC-001", "INC-002", "INC-003"],
        "change": {"incident_id": "INC-002", "note": "trapped people reported",
                   "changes": {"severity": 5, "hazard_level": 5, "affected_people_num": 8,
                               "affected_people": "8 people trapped"}},
    })
    assert r.status_code == 200
    j = r.json()
    assert "before" in j and "after" in j


def test_reassess_incident(client):
    r = client.post("/api/incidents/INC-003/reassess",
                    json={"changes": {"severity": 5, "hazard_level": 4, "affected_people_num": 12},
                          "note": "worsening outage"})
    assert r.status_code == 200
    j = r.json()
    assert j["before"]["decision"]["preliminary_score"] < j["after"]["decision"]["preliminary_score"]


def test_dashboard_summary(client):
    client.post("/api/decisions/evaluate", json={"incident_id": "INC-001"})
    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    j = r.json()
    assert j["active_incidents"] >= 5
    assert j["total_decisions"] >= 1
    assert "resources" in j and len(j["resources"]) > 0


def test_demo_reset(client):
    client.post("/api/decisions/evaluate", json={"incident_id": "INC-001"})
    assert len(client.get("/api/decisions").json()) >= 1
    r = client.post("/api/demo/reset")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert len(client.get("/api/decisions").json()) == 0


def test_activity(client):
    client.post("/api/decisions/evaluate", json={"incident_id": "INC-001"})
    r = client.get("/api/activity")
    assert r.status_code == 200
    assert len(r.json()["activity"]) >= 1
