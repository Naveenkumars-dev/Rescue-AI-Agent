"""Orchestrator: evaluation, Decision Arena, reassessment, approval, safety, errors."""

from __future__ import annotations

import pytest

from app.agents.orchestrator import orchestrator
from app.schemas.models import Priority
from app.storage.store import store


# --- per-incident evaluation (demo mode) ---------------------------------------------


def test_evaluate_incident_demo_produces_full_decision():
    r = orchestrator.evaluate_incident("INC-001")
    assert r.decision.incident_id == "INC-001"
    assert r.decision.priority in Priority
    assert r.decision.live_decider is False  # no key configured
    assert r.mode == "demo"
    # every tool in the workflow was actually called
    names = [t.name for t in r.tool_calls]
    for required in ["get_incident_details", "list_active_incidents", "calculate_preliminary_risk",
                     "get_resource_status", "identify_information_gaps", "propose_response_plan",
                     "save_decision_record"]:
        assert required in names
    # structured decision saved to the store
    assert store.get_decision(r.decision_id) is not None


def test_evaluate_incident_missing_incident_raises():
    with pytest.raises(ValueError):
        orchestrator.evaluate_incident("INC-999")


# --- safety constraints --------------------------------------------------------------


def test_life_safety_incident_is_blocked():
    # INC-001 flood with possible trapped residents -> block in demo fallback
    r = orchestrator.evaluate_incident("INC-001")
    assert r.decision.triage_action.value == "block"
    assert r.decision.priority == Priority.CRITICAL
    assert r.decision.human_review_required is True


def test_minor_incident_is_allowed():
    # INC-002 road obstruction, no injuries -> allow / monitor
    r = orchestrator.evaluate_incident("INC-002")
    assert r.decision.triage_action.value == "allow"


# --- missing information ------------------------------------------------------------


def test_missing_information_flags_review():
    r = orchestrator.evaluate_incident("INC-001")  # has unknown affected people
    # either blocked (life safety) or, for an info-gap incident, decision_status NEEDS_MORE_INFORMATION
    assert r.decision.human_review_required is True
    assert isinstance(r.decision.missing_information, list)


# --- decision arena (competing incidents) --------------------------------------------


def test_arena_ranks_competing_incidents():
    a = orchestrator.evaluate_arena(["INC-001", "INC-002", "INC-003"])
    assert len(a.ranking) == 3
    assert a.ranking[0].incident_id == "INC-001"  # life-safety block first
    # ranks are sequential and start at 1
    assert [r.rank for r in a.ranking] == [1, 2, 3]
    # explanation includes the order
    assert "INC-001" in a.explanation
    assert a.trade_offs and a.what_could_change_it


def test_arena_skips_unknown_incidents():
    a = orchestrator.evaluate_arena(["INC-001", "INC-999"])
    assert len(a.ranking) == 1


# --- reassessment (the core demo: decision changes with new evidence) ----------------


def test_reassess_changes_decision_when_conditions_worsen():
    before = orchestrator.evaluate_incident("INC-003")  # power outage, low
    re = orchestrator.reassess("INC-003",
                               {"severity": 5, "hazard_level": 4, "affected_people_num": 12,
                                "affected_people": "~12 people affected"})
    assert re.before.decision.preliminary_score < re.after.decision.preliminary_score
    assert re.before.decision.priority != re.after.decision.priority
    # the store now reflects the updated incident
    assert store.get_incident("INC-003")["severity"] == 5


def test_reassess_arena_before_after():
    out = orchestrator.arena_reassess(["INC-001", "INC-002", "INC-003"],
                                      {"incident_id": "INC-002",
                                       "changes": {"severity": 5, "hazard_level": 5,
                                                   "affected_people_num": 8,
                                                   "affected_people": "8 people trapped"},
                                       "note": "road now blocks emergency access with trapped people"})
    assert "before" in out and "after" in out
    # INC-002 should rise in the ranking after becoming a life-safety incident
    before_rank = {r.incident_id: r.rank for r in out["before"].ranking}
    after_rank = {r.incident_id: r.rank for r in out["after"].ranking}
    assert after_rank["INC-002"] <= before_rank["INC-002"]


# --- decision history ----------------------------------------------------------------


def test_decision_history_accumulates():
    assert len(store.list_decisions()) == 0
    orchestrator.evaluate_incident("INC-001")
    orchestrator.evaluate_incident("INC-002")
    assert len(store.list_decisions()) == 2
    mine = store.list_decisions("INC-002")
    assert len(mine) == 1 and mine[0]["incident_id"] == "INC-002"


# --- approval / rejection ------------------------------------------------------------


def test_approve_and_reject_update_status():
    r = orchestrator.evaluate_incident("INC-002")
    approved = orchestrator.approve(r.decision_id, "looks good")
    assert approved["decision_status"] == "APPROVED"
    r2 = orchestrator.evaluate_incident("INC-003")
    rejected = orchestrator.reject(r2.decision_id, "insufficient info")
    assert rejected["decision_status"] == "REJECTED"


def test_approve_unknown_decision_returns_none():
    assert orchestrator.approve("DEC-9999") is None


# --- model errors / timeouts fall back gracefully ------------------------------------


def test_live_decider_error_falls_back_to_simulated(fake_decider, monkeypatch):
    # configure the fake decider to raise on ask, simulating a timeout / 5xx
    class BoomDecider:
        last_latency_ms = 0
        def ask(self, *a, **k):
            raise RuntimeError("simulated 503 / timeout")
        def health(self):
            return {"status": "ok"}

    def _boom(self):
        return BoomDecider()

    from app.agents import orchestrator as orch

    monkeypatch.setattr(orch.Orchestrator, "_get_decider", _boom)
    r = orchestrator.evaluate_incident("INC-002")
    assert r.decision.live_decider is False  # fell back to simulated
    assert r.decision.mode == "demo"


def test_live_decider_drives_priority(fake_decider):
    # the real decision path: fake decider says high priority, recommend plan, not life-safety
    fake_decider.responses = {
        "life_safety": {"p_yes": 0.05},
        "priority": {"probabilities": {"low": 0.05, "medium": 0.1, "high": 0.8, "critical": 0.05}},
        "next_action": {"label": "recommend_response_plan",
                        "probabilities": {"recommend_response_plan": 0.9, "monitor": 0.1}},
    }
    r = orchestrator.evaluate_incident("INC-002")
    assert r.decision.live_decider is True
    assert r.decision.priority == Priority.HIGH
    assert r.decision.triage_action.value == "allow"
    assert r.decision.decider_evidence is not None
    assert r.decision.decider_evidence.priority_probabilities["high"] == 0.8


def test_live_decider_blocks_life_safety(fake_decider):
    fake_decider.responses = {
        "life_safety": {"p_yes": 0.85},
        "priority": {"probabilities": {"low": 0.05, "medium": 0.05, "high": 0.1, "critical": 0.8}},
        "next_action": {"label": "escalate_to_human",
                        "probabilities": {"escalate_to_human": 0.9, "monitor": 0.1}},
    }
    r = orchestrator.evaluate_incident("INC-001")
    assert r.decision.triage_action.value == "block"
    assert r.decision.priority == Priority.CRITICAL
    assert r.decision.human_review_required is True
