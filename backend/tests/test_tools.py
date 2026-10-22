"""Agent tool behavior tests."""

from __future__ import annotations

from app.tools import core as tools


def test_get_incident_details_found_and_missing():
    inc = tools.get_incident_details("INC-001")
    assert inc["id"] == "INC-001"
    assert inc["type"] == "flood"
    assert "preliminary_score" in inc
    missing = tools.get_incident_details("INC-999")
    assert "error" in missing


def test_list_active_incidents_ranked():
    out = tools.list_active_incidents()
    assert out["count"] >= 3
    scores = [i["preliminary_score"] for i in out["active_incidents"]]
    assert scores == sorted(scores, reverse=True)


def test_get_resource_status_matching():
    out = tools.get_resource_status("flood")
    assert out["incident_type"] == "flood"
    assert any("Rescue" in r["name"] or "Boat" in r["name"] for r in out["available_resources"])
    empty = tools.get_resource_status("zzz-no-such-type")
    assert empty["any_available"] is False


def test_calculate_preliminary_risk_bounds_and_weights():
    low = tools.calculate_preliminary_risk(1, 1, 0, 1)
    high = tools.calculate_preliminary_risk(5, 5, 50, 5)
    assert 0 <= low["preliminary_score"] <= 100
    assert 0 <= high["preliminary_score"] <= 100
    assert high["preliminary_score"] > low["preliminary_score"]
    # severity weight (30) dominates when others are equal
    assert tools.calculate_preliminary_risk(5, 1, 0, 1)["preliminary_score"] > \
        tools.calculate_preliminary_risk(1, 1, 0, 1)["preliminary_score"]


def test_identify_information_gaps_for_unknown_people():
    out = tools.identify_information_gaps("INC-001")
    # INC-001 flood reports residents "may be trapped" with unknown people count
    assert out["has_gaps"] is True
    assert any("people" in g for g in out["missing_information"])


def test_identify_information_gaps_from_report_text():
    out = tools.identify_information_gaps(report="A small fire with no injuries reported.")
    assert isinstance(out["missing_information"], list)


def test_compare_incidents_structured_evidence():
    out = tools.compare_incidents(["INC-001", "INC-002", "INC-003"])
    assert len(out["comparison"]) == 3
    ids = {r["incident_id"] for r in out["comparison"]}
    assert ids == {"INC-001", "INC-002", "INC-003"}
    # each row carries the transparent score and resource availability flag
    for row in out["comparison"]:
        assert "preliminary_score" in row
        assert "resources_available" in row


def test_propose_response_plan_shape():
    plan = tools.propose_response_plan("INC-001", "CRITICAL", "deploy boats", "Rescue Boat x2")
    assert plan["response_plan"]["priority"] == "CRITICAL"
    assert plan["response_plan"]["human_review_required"] is True


def test_save_decision_record_persists():
    from app.storage.store import store

    before = len(store.list_decisions())
    out = tools.save_decision_record({"incident_id": "INC-001", "priority": "CRITICAL",
                                       "decision_status": "PROPOSED"})
    assert out["recorded"] is True
    assert out["decision_id"].startswith("DEC-")
    assert len(store.list_decisions()) == before + 1


def test_tool_calls_are_logged():
    log: list = []
    tools.get_incident_details("INC-001", log)
    tools.list_active_incidents(log)
    names = [e["name"] for e in log]
    assert names == ["get_incident_details", "list_active_incidents"]
