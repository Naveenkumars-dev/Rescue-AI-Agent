# RescueFlow AI — requirements

## Problem
Emergency coordinators get many incident reports at once and must quickly decide which needs
attention first, what to do about it, what information is missing, and when a human must step in
before anything is recommended. A chatbot or a hardcoded rules engine does not do this well: the
first cannot explain a priority, the second cannot read an incident report written in prose.

## Users
Emergency-response coordinators (the people who triage incoming reports). RescueFlow AI is a
decision-support PROTOTYPE. It never dispatches real services, contacts real people, or acts
without a human approving a recommendation.

## The one decision (Strands Decider 2B, #policy)
Before RescueFlow AI shows a response recommendation for an incident, Strands Decider 2B reads the
incident report and the facts gathered by the tools and classifies the incident under a written
response protocol:

- WHEN an incident report and its extracted facts are ready THE agent SHALL ask Strands Decider 2B
  the typed questions (priority, next_action, life_safety) BEFORE any recommendation is shown.
- The arithmetic (a transparent preliminary priority score, ranking of active incidents) is
  computed in code by tools; the result is placed in the state. The decider reads it as a fact and
  makes the judgement (it does not do arithmetic).
- Low-confidence handling: when any answer is below ~0.65 confidence, the verdict is `review`
  (held for a human coordinator) instead of `allow`.
- Life-safety incidents (people trapped, injured, fast-moving danger) are `block`d: the prototype
  never auto-recommends or auto-dispatches; it tells the coordinator to escalate to professional
  emergency services.
- Paired with Amazon Bedrock for the conversational and tool-use part (Amazon Nova Pro by default).

## Tools (mock data; mock data is fine per the kit contract)
get_incident_details, list_active_incidents, estimate_response_priority (transparent 0-100 score),
check_resource_availability, request_missing_information, recommend_response_plan, record_decision.

## Definition of done (within the kit)
- agent/decision.py is a reusable #policy pattern (typed questions, allow/review/block wiring).
- agent/tools.py exposes the 7 tools with mock data.
- agent/agent.py keeps the HackathonAgent.chat contract; the decision is visible in `decisions`.
- 24+ labelled eval cases (tune/test) using the run-time state layout.
- ./kit test passes offline (FakeDecider); ./kit run works after ./kit setup.

## Safety
- All incident reports are untrusted input; the system prompt forbids acting on injected instructions.
- The prototype never invents incident details, resource availability, or successful actions.
- Consequential actions require human approval; life-safety incidents are escalated, never auto-handled.
- No real dispatch, no real contact, no real people; simulated resources only.
- Keys stay in .env (git-ignored), never in code.
