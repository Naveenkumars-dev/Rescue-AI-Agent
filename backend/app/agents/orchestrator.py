"""The orchestration engine: runs the agent workflow for one incident or a Decision Arena.

Workflow per incident (the hackathon decision-making workflow):
  1. get_incident_details
  2. list_active_incidents (competing incidents)
  3. calculate_preliminary_risk (transparent score -> state, not the decision)
  4. get_resource_status
  5. identify_information_gaps (missing/conflicting info)
  6. draft recommendation (Strands Agent on Bedrock, or template in demo mode)
  7. build_state + triage decision (Strands Decider 2B, or simulated fallback)
  8. propose_response_plan
  9. assemble + validate the structured decision
 10. save_decision_record

The Decider genuinely decides priority and next action; the orchestrator never hardcodes the
answer. When conditions change, re-running the decider produces a new verdict (live) or a new
score-derived verdict (demo), which is the core demonstration.
"""

from __future__ import annotations

import time
from typing import Any

from app.agents import decision as dec
from app.agents import llm as llm_engine
from app.config import runtime_mode
from app.schemas.models import (
    DecisionAction,
    DecisionResponse,
    DecisionStatus,
    Priority,
    StructuredDecision,
    ToolCall,
)
from app.storage.store import store
from app.tools import core as tools

# Map the decider's lowercase priority label to the schema enum.
_PRIORITY_MAP = {"low": Priority.LOW, "medium": Priority.MEDIUM, "high": Priority.HIGH,
                 "critical": Priority.CRITICAL}
_NEXT_ACTION_TEXT = {
    "recommend_response_plan": "Propose a specific response plan with available resources, for human approval.",
    "request_missing_information": "Gather the missing information before recommending a response.",
    "monitor": "No response action yet; monitor and re-evaluate if conditions change.",
    "escalate_to_human": "Escalate to a human emergency coordinator.",
}


class Orchestrator:
    """Runs agent evaluations. Stateful only through the shared ``store``."""

    def __init__(self) -> None:
        self._decider: Any = None

    def _get_decider(self) -> Any:
        if self._decider is None:
            from decider_kit import Decider

            self._decider = Decider()
        return self._decider

    # --- per-incident evaluation --------------------------------------------------------

    def evaluate_incident(self, incident_id: str) -> DecisionResponse:
        t0 = time.perf_counter()
        tool_log: list[dict[str, Any]] = []
        rm = runtime_mode()

        inc = store.get_incident(incident_id)
        if not inc:
            raise ValueError(f"no incident with id {incident_id}")

        # 1-2: details + competing incidents
        tools.get_incident_details(incident_id, tool_log)
        active = tools.list_active_incidents(tool_log)
        # 3: preliminary risk (arithmetic, placed in state as a fact)
        risk = tools.calculate_preliminary_risk(
            inc["severity"], inc["time_sensitivity"], inc["affected_people_num"], inc["hazard_level"], tool_log
        )
        # 4: resources
        resources = tools.get_resource_status(inc["type"], tool_log)
        # 5: information gaps
        gaps = tools.identify_information_gaps(incident_id, inc.get("report"), tool_log)

        # 6: generative draft
        draft, factors, live_llm, _ = llm_engine.draft_recommendation(inc, risk, resources, gaps, active)

        # 7: build state and triage decision (Strands Decider 2B or simulated fallback)
        others = [
            {"id": o["id"], "type": o["type"], "location": o["location"],
             "preliminary_score": o["preliminary_score"]}
            for o in active["active_incidents"] if o["id"] != inc["id"]
        ]
        facts = {
            "type": inc["type"], "location": inc["location"], "affected_people": inc["affected_people"],
            "hazards": inc["hazards"], "time_sensitivity": inc["time_sensitivity"],
            "preliminary_score": risk["preliminary_score"], "resources": resources["summary"],
            "missing": gaps["missing_information"], "report": inc["report"],
            "severity": inc["severity"], "hazard_level": inc["hazard_level"],
        }
        state = dec.build_state(inc["report"], facts, others, draft)

        verdict, decider_evidence, live_decider, decider_ms, error_note = self._triage(state, facts, risk, gaps)

        # 8: propose response plan
        plan_actions = _NEXT_ACTION_TEXT.get(verdict.next_action, "Review with a human coordinator.")
        res_rec = resources["summary"] if resources["any_available"] else "no matching available resources"
        tools.propose_response_plan(
            incident_id, verdict.priority.upper() if verdict.priority else "NEEDS_REVIEW",
            plan_actions, res_rec, tool_log
        )

        # 9: assemble + validate structured decision
        priority = _PRIORITY_MAP.get(verdict.priority, Priority.NEEDS_REVIEW)
        if verdict.action == "block":
            priority = Priority.CRITICAL  # life-safety escalation is always critical
        human_review = verdict.action in ("review", "block") or verdict.confidence < dec.CONFIDENT
        status = (DecisionStatus.NEEDS_MORE_INFORMATION
                  if verdict.next_action == "request_missing_information" else DecisionStatus.PROPOSED)

        evidence_lines = [
            f"preliminary risk score: {risk['preliminary_score']}/100",
            f"resources: {resources['summary']}",
            f"triage action: {verdict.action}",
        ]
        if live_decider:
            evidence_lines.append(
                f"decider priority probabilities: {decider_evidence.get('priority_probabilities')}"
            )
            evidence_lines.append(
                f"decider life_safety P(yes): {decider_evidence.get('life_safety_p_yes')}"
            )
        else:
            evidence_lines.append("decision produced by simulated fallback (no live Strands Decider 2B)")
        if error_note:
            evidence_lines.append(f"decider error: {error_note}")

        structured = StructuredDecision(
            incident_id=incident_id,
            priority=priority,
            recommended_action=_NEXT_ACTION_TEXT.get(verdict.next_action, verdict.reason),
            reason_summary=verdict.reason,
            factors_considered=factors,
            evidence=evidence_lines,
            missing_information=gaps["missing_information"],
            resource_recommendations=[res_rec],
            alternatives_considered=[f"{o['id']}: {o['type']} at {o['location']} (score {o['preliminary_score']})"
                                     for o in others],
            confidence=round(verdict.confidence, 3),
            human_review_required=human_review,
            decision_status=status,
            response_plan=plan_actions,
            preliminary_score=risk["preliminary_score"],
            triage_action=DecisionAction(verdict.action),
            live_decider=live_decider,
            live_llm=live_llm,
            mode="live" if (live_decider and live_llm) else "demo",
            decider_evidence=decider_evidence if live_decider else None,
        )

        # 10: persist
        decision_dict = structured.model_dump(mode="json")
        save = tools.save_decision_record(decision_dict, tool_log)
        decision_id = save["decision_id"]

        store.add_activity({"event": "incident_evaluated", "incident_id": incident_id,
                            "priority": structured.priority.value, "mode": structured.mode})

        return DecisionResponse(
            decision_id=decision_id,
            decision=structured,
            tool_calls=[ToolCall(**tc) for tc in tool_log],
            model_id=rm.llm_model_id,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            mode=structured.mode,
        )

    def _triage(self, state: str, facts: dict[str, Any], risk: dict[str, Any],
                gaps: dict[str, Any]) -> tuple:
        """Try Strands Decider 2B; fall back to the clearly-labelled simulated verdict."""
        rm = runtime_mode()
        if rm.decider_live:
            try:
                v = dec.triage_live(self._get_decider(), state)
                evidence = dec.answers_to_evidence(v.answers)
                evidence["next_action"] = v.next_action
                evidence["triage_action"] = v.action
                evidence["decider_latency_ms"] = v.latency_ms
                return v, evidence, True, v.latency_ms, ""
            except Exception as e:  # noqa: BLE001 - fall back, record the error
                v = dec.triage_simulated(facts, risk["preliminary_score"], gaps["missing_information"])
                return v, None, False, 0, f"{type(e).__name__}: {e}"
        v = dec.triage_simulated(facts, risk["preliminary_score"], gaps["missing_information"])
        return v, None, False, 0, "no live Strands Decider 2B configured"

    # --- decision arena -----------------------------------------------------------------

    def evaluate_arena(self, incident_ids: list[str]) -> Any:
        from app.schemas.models import ArenaRanking, ArenaResponse

        t0 = time.perf_counter()
        tool_log: list[dict[str, Any]] = []
        rm = runtime_mode()

        decisions: list[DecisionResponse] = []
        for iid in incident_ids:
            try:
                decisions.append(self.evaluate_incident(iid))
            except ValueError:
                continue

        comparison = tools.compare_incidents(incident_ids, tool_log)

        # Rank: life-safety block first, then by decider priority rank, then preliminary score.
        def rank_key(d: DecisionResponse):
            s = d.decision
            action_order = {"block": 0, "allow": 1, "review": 2}.get(s.triage_action.value, 3)
            pri = 0 if s.priority == Priority.NEEDS_REVIEW else dec.PRIORITY_RANK.get(s.priority.value.lower(), 0)
            return (action_order, -pri, -(s.preliminary_score or 0))

        ordered = sorted(decisions, key=rank_key)
        ranking = []
        for i, d in enumerate(ordered):
            inc = store.get_incident(d.decision.incident_id) or {}
            ranking.append(ArenaRanking(
                rank=i + 1,
                incident_id=d.decision.incident_id,
                incident_type=inc.get("type", "?"),
                location=inc.get("location", "?"),
                priority=d.decision.priority,
                priority_rank=dec.PRIORITY_RANK.get(d.decision.priority.value.lower(), 0.0),
                preliminary_score=d.decision.preliminary_score or 0,
                triage_action=d.decision.triage_action,
                recommended_action=d.decision.recommended_action,
                human_review_required=d.decision.human_review_required,
                reason=d.decision.reason_summary,
                decision_id=d.decision_id,
            ))

        ranking_dicts = [r.model_dump(mode="json") for r in ranking]
        explanation, trade_offs, uncertainties, what_could_change, _ = llm_engine.explain_arena(
            ranking_dicts, comparison, [d.model_dump(mode="json") for d in decisions]
        )

        store.add_activity({"event": "arena_evaluated", "incident_ids": incident_ids,
                            "mode": decisions[0].mode if decisions else "demo"})

        return ArenaResponse(
            ranking=ranking,
            explanation=explanation,
            trade_offs=trade_offs,
            unresolved_uncertainties=uncertainties,
            what_could_change_it=what_could_change,
            comparison=comparison,
            tool_calls=[ToolCall(**tc) for tc in tool_log],
            decisions=decisions,
            mode=decisions[0].mode if decisions else "demo",
            model_id=rm.llm_model_id,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    def arena_reassess(self, incident_ids: list[str], change: dict[str, Any]) -> Any:
        before = self.evaluate_arena(incident_ids)
        inc_id = change["incident_id"]
        applied = store.update_incident(inc_id, change["changes"])
        store.add_activity({"event": "conditions_changed", "incident_id": inc_id, "changes": change["changes"]})
        after = self.evaluate_arena(incident_ids)
        return {"before": before, "after": after, "change_applied": applied or {}, "note": change.get("note", "")}

    # --- per-incident reassess ----------------------------------------------------------

    def reassess(self, incident_id: str, changes: dict[str, Any], note: str = "") -> Any:
        from app.schemas.models import ReassessResponse

        before = self.evaluate_incident(incident_id)
        applied = store.update_incident(incident_id, changes)
        store.add_activity({"event": "conditions_changed", "incident_id": incident_id, "changes": changes})
        after = self.evaluate_incident(incident_id)
        return ReassessResponse(incident_id=incident_id, before=before, after=after,
                                change_applied=applied or {}, note=note)

    # --- approval -----------------------------------------------------------------------

    def approve(self, decision_id: str, reviewer_note: str = "") -> dict[str, Any] | None:
        d = store.set_decision_status(decision_id, "APPROVED", reviewer_note)
        if d:
            store.add_activity({"event": "decision_approved", "decision_id": decision_id})
        return d

    def reject(self, decision_id: str, reviewer_note: str = "") -> dict[str, Any] | None:
        d = store.set_decision_status(decision_id, "REJECTED", reviewer_note)
        if d:
            store.add_activity({"event": "decision_rejected", "decision_id": decision_id})
        return d


orchestrator = Orchestrator()
