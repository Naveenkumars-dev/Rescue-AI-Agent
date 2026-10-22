"""Wiring tests for the RescueFlow AI triage decision pattern (#policy).

Covers the allow/review/block verdict logic, the state layout, and the tools. Uses FakeDecider
for the decider path and constructs Decision objects directly to hit the low-confidence branch.
"""

from __future__ import annotations

from decider_kit.client import Decision

from agent.decision import PATTERN_TAG, QUESTIONS, TriagePolicy, build_state
from agent.tools import (
    DECISIONS, TURN_CONTEXT, clear_turn_context, preliminary_score,
)


def _decs(life_safety_p, life_safety_conf, next_action, na_conf, priority, pri_conf):
    return {
        "life_safety": Decision("noul", {}, p_yes=life_safety_p,
                                 label="yes" if life_safety_p >= 0.5 else "no",
                                 confidence=life_safety_conf),
        "next_action": Decision("choice", {}, label=next_action, confidence=na_conf,
                                probabilities={next_action: na_conf}),
        "priority": Decision("score", {}, label=priority, confidence=pri_conf,
                             probabilities={priority: pri_conf}),
    }


def _policy():
    return TriagePolicy(decider=None)  # decide() never calls the decider


def test_pattern_tag_and_questions():
    assert PATTERN_TAG == "#policy"
    assert set(QUESTIONS) == {"priority", "next_action", "life_safety"}
    assert QUESTIONS["priority"]["type"] == "score"
    assert QUESTIONS["next_action"]["type"] == "choice"
    assert QUESTIONS["life_safety"]["type"] == "noul"


def test_blocks_clear_life_safety():
    v = _policy().decide(_decs(0.92, 0.92, "escalate_to_human", 0.85, "critical", 0.8))
    assert v.action == "block"


def test_review_on_ambiguous_life_safety():
    v = _policy().decide(_decs(0.5, 0.5, "escalate_to_human", 0.85, "critical", 0.8))
    assert v.action == "review"
    assert "life-safety" in v.reason.lower()


def test_review_on_escalate_to_human():
    v = _policy().decide(_decs(0.1, 0.9, "escalate_to_human", 0.85, "high", 0.8))
    assert v.action == "review"


def test_review_on_request_missing_information():
    v = _policy().decide(_decs(0.1, 0.9, "request_missing_information", 0.85, "medium", 0.8))
    assert v.action == "review"


def test_review_on_low_confidence():
    v = _policy().decide(_decs(0.1, 0.9, "recommend_response_plan", 0.85, "low", 0.4))
    assert v.action == "review" and "confidence" in v.reason.lower()


def test_allows_recommend_response_plan():
    v = _policy().decide(_decs(0.1, 0.9, "recommend_response_plan", 0.85, "low", 0.8))
    assert v.action == "allow"


def test_allows_monitor():
    v = _policy().decide(_decs(0.1, 0.9, "monitor", 0.85, "low", 0.8))
    assert v.action == "allow"


def test_check_logs_a_record_with_verdict_and_decider_ms():
    from fakes import FakeDecider

    rule = lambda state, name, q: (0.92 if name == "life_safety" else "escalate_to_human" if name == "next_action" else "critical")
    p = TriagePolicy(FakeDecider(rule))
    v = p.check(build_state("Fire with people inside.", {"type": "fire", "preliminary_score": 95}, [], "Escalate."))
    assert v.action == "block"
    rec = p.log[-1]
    assert rec["verdict"] == "block" and rec["pattern"] == "#policy" and rec["decider_ms"] >= 0
    assert rec["life_safety_p_yes"] == 0.92


def test_build_state_contains_every_section():
    s = build_state("Flood at Riverside.", {"type": "flood", "location": "Riverside", "preliminary_score": 100,
                  "resources": "boats", "missing": ["number affected"]},
                    [{"id": "INC-002", "type": "road obstruction", "location": "Oak Lane", "preliminary_score": 27}],
                    "Draft: escalate.")
    for needle in ("RESPONSE PROTOCOL", "INCIDENT REPORT", "Flood at Riverside.", "EXTRACTED FACTS",
                   "incident type: flood", "preliminary priority score: 100", "available resources: boats",
                   "missing information flagged: number affected", "OTHER ACTIVE INCIDENTS",
                   "INC-002: road obstruction at Oak Lane", "DRAFT RECOMMENDATION", "Draft: escalate."):
        assert needle in s, needle


def test_preliminary_score_is_bounded_and_monotonic():
    assert preliminary_score(1, 1, 0, 1) == 0 or preliminary_score(1, 1, 0, 1) >= 0
    assert preliminary_score(5, 5, 50, 5) == 100
    assert preliminary_score(5, 5, 0, 5) > preliminary_score(1, 1, 0, 1)


def test_tool_functions_run_against_mock_data():
    from agent.tools import (check_resource_availability, estimate_response_priority,
                             get_incident_details, list_active_incidents, record_decision,
                             recommend_response_plan, request_missing_information)

    clear_turn_context()
    DECISIONS.clear()
    assert get_incident_details("inc-001")["id"] == "INC-001"
    assert get_incident_details("NOPE")["error"].startswith("no registered")
    active = list_active_incidents()
    assert active["count"] >= 1 and active["active_incidents"][0]["preliminary_score"] >= active["active_incidents"][-1]["preliminary_score"]
    est = estimate_response_priority(5, 5, 3, 4)
    assert 0 <= est["preliminary_score"] <= 100 and est["breakdown"]["severity"] == 5
    res = check_resource_availability("flood")
    assert "summary" in res and res["incident_type"] == "flood"
    miss = request_missing_information("location, people affected")
    assert miss["missing_information"] == ["location", "people affected"]
    plan = recommend_response_plan("INC-002", "medium", "clear branch", "Road Clearance Crew x4")
    assert plan["status"] == "PROPOSED" and plan["human_review_required"] is True
    rec = record_decision("INC-002", "propose clearing", "low risk", "PROPOSED")
    assert rec["recorded"] and DECISIONS[-1]["status"] == "PROPOSED"
