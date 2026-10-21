"""Decision pattern and structured-decision validation tests."""

from __future__ import annotations

from app.agents import decision as dec
from app.schemas.models import Priority, StructuredDecision


def _fake_answers(life_safety_p_yes=0.1, life_safety_conf=0.9, priority_label="high",
                 priority_conf=0.9, next_action="recommend_response_plan", next_conf=0.9):
    """Build the dict of Decision objects the decider would return."""
    class D:
        def __init__(self, kind, label=None, p_yes=None, probabilities=None, confidence=0.9):
            self.kind = kind
            self.label = label
            self.p_yes = p_yes
            self.probabilities = probabilities or {}
            self.confidence = confidence

    return {
        "life_safety": D("noul", p_yes=life_safety_p_yes, confidence=life_safety_conf,
                         probabilities={"yes": life_safety_p_yes, "no": 1 - life_safety_p_yes}),
        "priority": D("score", label=priority_label,
                      probabilities={"low": 0.05, "medium": 0.1, "high": 0.8, "critical": 0.05},
                      confidence=priority_conf),
        "next_action": D("choice", label=next_action,
                         probabilities={next_action: 0.9, "monitor": 0.1}, confidence=next_conf),
    }


def test_build_state_includes_protocol_report_and_facts():
    state = dec.build_state("Flood at Riverside.", {"type": "flood", "location": "Riverside",
        "affected_people": "unknown", "hazards": "rising water", "time_sensitivity": 5,
        "preliminary_score": 80, "resources": "Boats x2"}, [], "draft plan")
    assert "RESPONSE PROTOCOL" in state
    assert "Flood at Riverside" in state
    assert "preliminary priority score: 80" in state
    assert "draft plan" in state


def test_decide_blocks_life_safety_when_confident():
    v = dec.decide(_fake_answers(life_safety_p_yes=0.8, life_safety_conf=0.9, priority_label="critical"))
    assert v.action == "block"


def test_decide_reviews_when_life_safety_ambiguous():
    v = dec.decide(_fake_answers(life_safety_p_yes=0.5, life_safety_conf=0.9, priority_label="high"))
    assert v.action == "review"


def test_decide_reviews_on_missing_information_action():
    v = dec.decide(_fake_answers(next_action="request_missing_information"))
    assert v.action == "review"


def test_decide_reviews_on_escalate_to_human():
    v = dec.decide(_fake_answers(next_action="escalate_to_human"))
    assert v.action == "review"


def test_decide_allows_monitor():
    v = dec.decide(_fake_answers(next_action="monitor", priority_label="low"))
    assert v.action == "allow"


def test_decide_allows_recommend_response_plan():
    v = dec.decide(_fake_answers(next_action="recommend_response_plan", priority_label="medium"))
    assert v.action == "allow"


def test_decide_falls_back_to_review_on_low_confidence():
    v = dec.decide(_fake_answers(life_safety_p_yes=0.1, life_safety_conf=0.3, priority_conf=0.3,
                                next_conf=0.3, next_action="recommend_response_plan"))
    assert v.action == "review"


def test_triage_simulated_is_labelled_and_non_calibrated():
    facts = {"report": "Flood with trapped residents", "hazards": "rising water",
             "severity": 5, "hazard_level": 5}
    v = dec.triage_simulated(facts, 80, [])
    assert v.live is False
    assert "SIMULATED" in v.reason
    assert v.action == "block"  # life-safety language + severity>=4 + hazard>=4
    # simulated confidence is a fixed marker, never a calibrated probability claim
    assert v.confidence == 0.45


def test_triage_simulated_missing_info_yields_review():
    v = dec.triage_simulated({"report": "Something happened", "hazards": "none", "severity": 3,
                              "hazard_level": 1}, 40, ["number of people affected"])
    assert v.action == "review"


def test_structured_decision_validates_all_priority_levels():
    for p in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NEEDS_REVIEW"]:
        d = StructuredDecision(incident_id="INC-001", priority=p, recommended_action="x",
                              reason_summary="y", confidence=0.5, human_review_required=True)
        assert d.priority == p


def test_structured_decision_validates_all_statuses():
    for s in ["PROPOSED", "APPROVED", "REJECTED", "NEEDS_MORE_INFORMATION"]:
        d = StructuredDecision(incident_id="INC-001", priority="LOW", recommended_action="x",
                              reason_summary="y", confidence=0.5, human_review_required=True,
                              decision_status=s)
        assert d.decision_status == s


def test_structured_decision_rejects_invalid_priority():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StructuredDecision(incident_id="INC-001", priority="URGENT", recommended_action="x",
                           reason_summary="y", confidence=0.5, human_review_required=True)


def test_confidence_field_is_bounded():
    d = StructuredDecision(incident_id="INC-001", priority="LOW", recommended_action="x",
                          reason_summary="y", confidence=1.0, human_review_required=False)
    assert d.confidence == 1.0
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StructuredDecision(incident_id="INC-001", priority="LOW", recommended_action="x",
                           reason_summary="y", confidence=1.5, human_review_required=False)
