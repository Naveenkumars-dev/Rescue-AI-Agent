"""REUSABLE DECISION PATTERN: emergency-response triage policy  (#policy)

What it does
    Before RescueFlow AI shows a response recommendation for an incident, Strands Decider 2B
    classifies the incident under a written emergency-response protocol and returns one of
    allow / review / block:
    - allow: the incident is clear, non-life-threatening and actionable; the prototype may propose
      a response plan with available resources, for a human coordinator to approve.
    - review: key information is missing or vague, the situation is borderline, or the decider is
      unsure; a human coordinator must gather more information or confirm before anything is shown.
    - block: the incident describes an immediate or probable threat to life or serious harm; it
      must be escalated to professional emergency services and a human coordinator, and the
      prototype must never auto-recommend or auto-dispatch a response for it.
    Every number (a transparent preliminary priority score, the ranking of active incidents) is
    computed in code by the tools and placed in the state as a fact; the decider reads it alongside
    the incident prose and makes the judgement. It does not do arithmetic.

Typed questions and options
    priority (score): triage priority of this incident. ["low", "medium", "high", "critical"]
    next_action (choice): the response action that fits right now.
        - recommend_response_plan: enough is clearly known, with resources available, to propose a specific response plan
        - request_missing_information: key details are missing or vague (location, number affected, hazard) and must be gathered first
        - monitor: no action is needed yet; the incident is minor or already contained; keep watching and re-evaluate if it changes
        - escalate_to_human: the situation is high-stakes or borderline; a human emergency coordinator must decide
    life_safety (noul): does the report describe an immediate or probable threat to life or serious
    harm that the protocol says must be escalated and never auto-handled by a prototype?

Wiring (where it sits in the agent's path)
    `TriagePolicy` is a plain check run in `agent/agent.py` AFTER the Strands agent (on Amazon
    Bedrock) has gathered facts with its tools and drafted a recommendation, and BEFORE the
    recommendation is shown:
        verdict = TriagePolicy(Decider()).check(state)
        if verdict.action == "block":   reply = escalation_message(...)
        elif verdict.action == "review": reply = hold_for_human(...)
        else:                             reply = draft + approval_note(...)
    One forward pass per turn; the verdict and its probabilities are appended to `.log` and shown
    in the demo's decision panel. The thresholds that turn probabilities into actions live in
    `decide()` — change them there, in code you own.

How to reuse it
    Copy this file, rewrite `PROTOCOL` and the three questions for your safety-critical domain, and
    keep the allow/review/block thresholds in `decide()`. Keep the rule: compute every number in a
    tool and put the result in the state; let the decider read language, not do arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from decider_kit import Decider, Decision

PATTERN_TAG = "#policy"

PROTOCOL = """\
- Life-safety incidents (people trapped, injured, or a fast-moving danger) must be escalated to
  professional emergency services and a human coordinator. This prototype never auto-dispatches
  or auto-recommends a response for them.
- When key details are missing or vague, gather them before recommending.
- When the situation is high-stakes or borderline, a human coordinator must confirm.
- Otherwise the prototype may propose a response plan with available resources, for human approval."""

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
        "Does this incident describe an immediate or probable threat to life or serious harm (people trapped, injured, or a fast-moving danger) that the response protocol says must be escalated to professional emergency services and never auto-handled by a prototype?",
        {"true": "an immediate or probable threat to life or serious harm is described",
         "false": "no imminent threat to life or serious harm is described"},
    ),
}

# Thresholds (in code, not the model)
LIFE_SAFETY_BLOCK = 0.6       # P(life-safety) at/above which, if confident, we block (escalate)
LIFE_SAFETY_AMBIGUOUS = 0.4   # between this and BLOCK the signal is uncertain -> human review
CONFIDENT = 0.65              # below this confidence on any question, fall back to human review


@dataclass
class Verdict:
    action: str  # allow | review | block
    priority: str
    next_action: str
    p_life_safety: float
    reason: str
    answers: dict[str, Decision] = field(repr=False, default_factory=dict)


def build_state(report: str, facts: dict[str, Any] | str, others: list[dict[str, Any]], draft: str) -> str:
    """The state the decider reads: the protocol, the report, the extracted facts (from tools,
    including the preliminary score), the other active incidents for comparison, and the draft
    recommendation. Eval cases use this same layout (generated from this function)."""
    if isinstance(facts, dict):
        f = facts
        missing = f.get("missing")
        facts_block = "\n".join([
            f"incident type: {f.get('type', 'unknown')}",
            f"location: {f.get('location', 'unknown')}",
            f"affected people: {f.get('affected_people', 'unknown')}",
            f"hazards: {f.get('hazards', 'unknown')}",
            f"time sensitivity: {f.get('time_sensitivity', 'unknown')}",
            f"preliminary priority score: {f.get('preliminary_score', 'unknown')} (0 low, 100 critical; computed by the estimate_response_priority tool)",
            f"available resources: {f.get('resources', 'unknown')}",
        ] + ([f"missing information flagged: {', '.join(missing)}"] if missing else []))
    else:
        facts_block = str(facts)
    if others:
        other_lines = "\n".join(
            f"- {o.get('id', '?')}: {o.get('type', '?')} at {o.get('location', '?')} — prelim score {o.get('preliminary_score', '?')}"
            for o in others
        )
    else:
        other_lines = "(none)"
    return (
        "RescueFlow AI — emergency-response triage. The decider classifies one incident under the\n"
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


class TriagePolicy:
    """The policy gate: one Strands Decider 2B call per incident classifies it allow/review/block."""

    def __init__(self, decider: Decider, life_safety_block: float = LIFE_SAFETY_BLOCK,
                 life_safety_ambiguous: float = LIFE_SAFETY_AMBIGUOUS, confident: float = CONFIDENT):
        self.decider = decider
        self.life_safety_block = life_safety_block
        self.life_safety_ambiguous = life_safety_ambiguous
        self.confident = confident
        self.log: list[dict[str, Any]] = []

    def check(self, state: str, images: Any = None) -> Verdict:
        a = self.decider.ask(state, QUESTIONS, images=images)
        v = self.decide(a)
        self.log.append({
            "pattern": PATTERN_TAG,
            "verdict": v.action,
            "priority": v.priority,
            "next_action": v.next_action,
            "p_life_safety": round(v.p_life_safety, 3),
            "priority_probs": {k: round(val, 3) for k, val in a["priority"].probabilities.items()},
            "next_action_probs": {k: round(val, 3) for k, val in a["next_action"].probabilities.items()},
            "life_safety_p_yes": round(a["life_safety"].p_yes or 0.0, 3),
            "confident": (
                a["life_safety"].confidence >= self.confident
                and a["priority"].confidence >= self.confident
                and a["next_action"].confidence >= self.confident
            ),
            "reason": v.reason,
            "decider_ms": round(self.decider.last_latency_ms or 0),
        })
        return v

    def decide(self, a: dict[str, Decision]) -> Verdict:
        ls = a["life_safety"]
        ls_p = ls.p_yes or 0.0
        ls_conf = ls.confidence
        na = a["next_action"].label or ""
        pri = a["priority"].label or ""
        low_conf = (
            ls_conf < self.confident
            or a["priority"].confidence < self.confident
            or a["next_action"].confidence < self.confident
        )

        if ls_p >= self.life_safety_block and ls_conf >= self.confident:
            reason = ("Life-safety incident detected. Escalate to professional emergency services and a "
                      "human coordinator. This prototype must not auto-recommend or dispatch.")
            return Verdict("block", pri, na, ls_p, reason, a)
        if ls_p >= self.life_safety_ambiguous:
            reason = "Possible life-safety concern but the signal is uncertain. A human coordinator must assess before any recommendation."
            return Verdict("review", pri, na, ls_p, reason, a)
        if na == "escalate_to_human":
            reason = "High-stakes or borderline situation. A human coordinator must decide."
            return Verdict("review", pri, na, ls_p, reason, a)
        if na == "request_missing_information":
            reason = "Key information is missing or vague. Gather it before recommending a response."
            return Verdict("review", pri, na, ls_p, reason, a)
        if low_conf:
            reason = "Decision confidence is low. A human coordinator should review before acting."
            return Verdict("review", pri, na, ls_p, reason, a)
        if na == "monitor":
            reason = "No response action is needed yet. Monitor the situation and re-evaluate if it changes."
            return Verdict("allow", pri, na, ls_p, reason, a)
        reason = "Clear, non-life-threatening and actionable. Propose a response plan with available resources, for human approval."
        return Verdict("allow", pri, na, ls_p, reason, a)
