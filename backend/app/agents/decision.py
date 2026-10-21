"""REUSABLE DECISION PATTERN: emergency-response triage policy  (#policy)

What it does
    Before RescueFlow AI shows a recommendation for an incident, Strands Decider 2B classifies the
    incident under a written emergency-response protocol and returns one of allow / review / block:
    - allow: the incident is clear, non-life-threatening and actionable; propose a response plan
      for a human coordinator to approve.
    - review: key information is missing or vague, the situation is borderline, or the decider is
      unsure; a human coordinator must gather more information or confirm first.
    - block: the incident describes an immediate or probable threat to life or serious harm; it
      must be escalated to professional emergency services and a human coordinator, and the
      prototype must never auto-recommend or auto-dispatch a response for it.
    Every number (a transparent preliminary priority score, the ranking of active incidents) is
    computed in code by the tools and placed in the state as a fact; the decider reads it alongside
    the incident prose and makes the judgement. It does not do arithmetic.

Typed questions and option set
    priority (score): triage priority of this incident. ["low", "medium", "high", "critical"]
    next_action (choice): the response action that fits right now.
        - recommend_response_plan
        - request_missing_information
        - monitor
        - escalate_to_human
    life_safety (noul): does the report describe an immediate or probable threat to life or
    serious harm that the protocol says must be escalated and never auto-handled by a prototype?

Wiring (where it sits in the agent's path)
    The orchestrator runs the tools, builds the state, then calls triage(state). In live mode
    this is one Strands Decider 2B forward pass; the verdict and its probabilities are shown in the
    decision panel. The thresholds that turn probabilities into actions live in decide() -- change
    them there, in code you own.

How to reuse it
    Copy this file, rewrite PROTOCOL and the three questions for your safety-critical domain, and
    keep the allow/review/block thresholds in decide(). Keep the rule: compute every number in a
    tool and put the result in the state; let the decider read language, not do arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from decider_kit import Decision, Decider, DeciderError

PATTERN_TAG = "#policy"

PROTOCOL = (
    "- Life-safety incidents (people trapped, injured, or a fast-moving danger) must be escalated "
    "to professional emergency services and a human coordinator. This prototype never auto-dispatches "
    "or auto-recommends a response for them.\n"
    "- When key details are missing or vague, gather them before recommending.\n"
    "- When the situation is high-stakes or borderline, a human coordinator must confirm.\n"
    "- Otherwise the prototype may propose a response plan with available resources, for human approval."
)

PRIORITY_LEVELS = ["low", "medium", "high", "critical"]

NEXT_ACTIONS = {
    "recommend_response_plan": "enough is clearly known, with resources available, to propose a specific response plan",
    "request_missing_information": "key details are missing or vague (location, number affected, hazard) and must be gathered before recommending",
    "monitor": "no response action is needed yet; the incident is minor or already contained; keep watching and re-evaluate if it changes",
    "escalate_to_human": "the situation is high-stakes or borderline; a human emergency coordinator must decide",
}

QUESTIONS = {
    "priority": Decider.score("How urgent is this incident for response priority?", PRIORITY_LEVELS),
    "next_action": Decider.choice(
        "Which response action fits this incident right now, given the facts and the other active incidents?",
        NEXT_ACTIONS,
    ),
    "life_safety": Decider.noul(
        "Does this incident describe an immediate or probable threat to life or serious harm "
        "(people trapped, injured, or a fast-moving danger) that the response protocol says must "
        "be escalated to professional emergency services and never auto-handled by a prototype?",
        {"true": "an immediate or probable threat to life or serious harm is described",
         "false": "no imminent threat to life or serious harm is described"},
    ),
}

# Thresholds (in code, not the model)
LIFE_SAFETY_BLOCK = 0.6       # P(life-safety) at/above which, if confident, we block (escalate)
LIFE_SAFETY_AMBIGUOUS = 0.4   # between this and BLOCK the signal is uncertain -> human review
CONFIDENT = 0.65              # below this confidence on any question, fall back to human review

PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class Verdict:
    action: str  # allow | review | block
    priority: str  # low | medium | high | critical (lowercase, from the decider) or ""
    next_action: str
    p_life_safety: float
    reason: str
    answers: dict[str, Decision] = field(repr=False, default_factory=dict)
    confidence: float = 0.0
    live: bool = True
    latency_ms: int = 0


def build_state(report: str, facts: dict[str, Any], others: list[dict[str, Any]], draft: str) -> str:
    """The state the decider reads: protocol, report, extracted facts (from tools, including the
    preliminary score), the other active incidents for comparison, and the draft recommendation."""
    missing = facts.get("missing")
    facts_block = "\n".join([
        f"incident type: {facts.get('type', 'unknown')}",
        f"location: {facts.get('location', 'unknown')}",
        f"affected people: {facts.get('affected_people', 'unknown')}",
        f"hazards: {facts.get('hazards', 'unknown')}",
        f"time sensitivity: {facts.get('time_sensitivity', 'unknown')}",
        f"preliminary priority score: {facts.get('preliminary_score', 'unknown')} (0 low, 100 critical; "
        "computed by the calculate_preliminary_risk tool)",
        f"available resources: {facts.get('resources', 'unknown')}",
    ] + ([f"missing information flagged: {', '.join(missing)}"] if missing else []))
    if others:
        other_lines = "\n".join(
            f"- {o.get('id', '?')}: {o.get('type', '?')} at {o.get('location', '?')} -- "
            f"prelim score {o.get('preliminary_score', '?')}"
            for o in others
        )
    else:
        other_lines = "(none)"
    return (
        "RescueFlow AI -- emergency-response triage. The decider classifies one incident under the\n"
        "response protocol below, before any recommendation is shown to a coordinator.\n\n"
        "--- RESPONSE PROTOCOL ---\n"
        f"{PROTOCOL}\n\n"
        "--- INCIDENT REPORT ---\n"
        f"{report.strip()}\n\n"
        "--- EXTRACTED FACTS (from tools) ---\n"
        f"{facts_block}\n\n"
        "--- OTHER ACTIVE INCIDENTS (for comparison) ---\n"
        f"{other_lines}\n\n"
        "--- DRAFT RECOMMENDATION (from the assistant, not yet shown) ---\n"
        f"{(draft or '').strip() or '(no draft yet)'}"
    )


def decide(answers: dict[str, Decision],
           life_safety_block: float = LIFE_SAFETY_BLOCK,
           life_safety_ambiguous: float = LIFE_SAFETY_AMBIGUOUS,
           confident: float = CONFIDENT) -> Verdict:
    """Turn Strands Decider 2B probabilities into an allow/review/block action (thresholds in code)."""
    ls = answers["life_safety"]
    ls_p = ls.p_yes or 0.0
    ls_conf = ls.confidence
    na = answers["next_action"].label or ""
    pri = answers["priority"].label or ""
    low_conf = (
        ls_conf < confident
        or answers["priority"].confidence < confident
        or answers["next_action"].confidence < confident
    )
    conf = min(ls.confidence, answers["priority"].confidence, answers["next_action"].confidence)

    if ls_p >= life_safety_block and ls_conf >= confident:
        reason = ("Life-safety incident detected by Strands Decider 2B. Escalate to professional "
                  "emergency services and a human coordinator. This prototype must not auto-recommend "
                  "or dispatch.")
        return Verdict("block", pri, na, ls_p, reason, answers, conf, True)
    if ls_p >= life_safety_ambiguous:
        reason = ("Possible life-safety concern but the decider's signal is uncertain. A human "
                  "coordinator must assess before any recommendation.")
        return Verdict("review", pri, na, ls_p, reason, answers, conf, True)
    if na == "escalate_to_human":
        reason = "High-stakes or borderline situation. A human coordinator must decide."
        return Verdict("review", pri, na, ls_p, reason, answers, conf, True)
    if na == "request_missing_information":
        reason = "Key information is missing or vague. Gather it before recommending a response."
        return Verdict("review", pri, na, ls_p, reason, answers, conf, True)
    if low_conf:
        reason = "Decision confidence is low. A human coordinator should review before acting."
        return Verdict("review", pri, na, ls_p, reason, answers, conf, True)
    if na == "monitor":
        reason = "No response action is needed yet. Monitor and re-evaluate if it changes."
        return Verdict("allow", pri, na, ls_p, reason, answers, conf, True)
    reason = ("Clear, non-life-threatening and actionable. Propose a response plan with available "
              "resources, for human approval.")
    return Verdict("allow", pri, na, ls_p, reason, answers, conf, True)


def triage_live(decider: Decider, state: str, images: list | None = None) -> Verdict:
    """One Strands Decider 2B forward pass over the state. Raises DeciderError if unreachable."""
    answers = decider.ask(state, QUESTIONS, images=images)
    v = decide(answers)
    v.latency_ms = int(decider.last_latency_ms or 0)
    return v


_LIFE_SAFETY_WORDS = ("trapped", "injured", "injury", "injuries", "unconscious", "fire", "flame",
                      "smoke", "gas leak", "collapse", "collapsed", "explosion", "drowning",
                      "swept away", "imminent", "life-threatening", "casualt")


def _priority_from_score(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def triage_simulated(facts: dict[str, Any], preliminary_score: int, missing: list[str]) -> Verdict:
    """A clearly-labelled deterministic fallback used ONLY when no live Strands Decider 2B is
    reachable. It never claims calibrated probabilities; confidence is a fixed heuristic marker.
    The same state/questions are used, but the judgement is rule-based and reported as simulated."""
    report = str(facts.get("report", "")) + " " + str(facts.get("hazards", ""))
    text = report.lower()
    life_words = [w for w in _LIFE_SAFETY_WORDS if w in text]
    high_life = bool(life_words) and facts.get("severity", 0) >= 4 and facts.get("hazard_level", 0) >= 4

    pri = _priority_from_score(preliminary_score)
    if high_life:
        p_life = 0.9
        action = "block"
        next_action = "escalate_to_human"
        reason = ("SIMULATED verdict (no live Strands Decider 2B): life-safety language detected. "
                  "Escalate to professional emergency services and a human coordinator.")
    elif missing:
        p_life = 0.3 if life_words else 0.05
        action = "review"
        next_action = "request_missing_information"
        reason = ("SIMULATED verdict (no live Strands Decider 2B): key information is missing. "
                  "Gather it before recommending.")
    elif preliminary_score <= 25:
        p_life = 0.02
        action = "allow"
        next_action = "monitor"
        reason = ("SIMULATED verdict (no live Strands Decider 2B): minor/contained. Monitor and "
                  "re-evaluate if it changes.")
    else:
        p_life = 0.1 if life_words else 0.02
        action = "allow"
        next_action = "recommend_response_plan"
        reason = ("SIMULATED verdict (no live Strands Decider 2B): clear and actionable. Propose a "
                  "response plan for human approval.")

    # A fixed, clearly non-calibrated confidence marker for the simulated path.
    confidence = 0.45
    return Verdict(action=action, priority=pri, next_action=next_action, p_life_safety=p_life,
                   reason=reason, answers={}, confidence=confidence, live=False, latency_ms=0)


def answers_to_evidence(answers: dict[str, Decision]) -> dict[str, Any]:
    """Serialize the raw decider answers for the decision panel."""
    return {
        "priority_probabilities": {k: round(v, 4) for k, v in answers["priority"].probabilities.items()},
        "next_action": answers["next_action"].label,
        "next_action_probabilities": {k: round(v, 4) for k, v in answers["next_action"].probabilities.items()},
        "life_safety_p_yes": round(answers["life_safety"].p_yes or 0.0, 4),
    }


__all__ = [
    "PATTERN_TAG", "PROTOCOL", "QUESTIONS", "PRIORITY_LEVELS", "NEXT_ACTIONS", "PRIORITY_RANK",
    "Verdict", "build_state", "decide", "triage_live", "triage_simulated", "answers_to_evidence",
]
