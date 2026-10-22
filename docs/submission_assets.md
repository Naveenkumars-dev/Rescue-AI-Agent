# Hackathon Submission Assets

---

## 150-word Article Summary

RescueFlow AI is an agentic decision-support prototype that helps emergency coordinators triage competing incident reports. During a disaster, multiple events arrive at once—a residential flood, a blocked road, a power outage—and a coordinator must decide which needs attention first, with incomplete information and changing conditions.

The system combines Amazon Bedrock (for the conversational and tool-use layer) with Strands Decider 2B (for triage classification). The agent gathers facts through eight explicitly defined tools, assembles a structured state, and calls Strands Decider 2B in one forward pass to answer three typed questions: priority level, recommended next action, and whether a life-safety threat is present. The verdict—*allow, review,* or *block*—is returned with probabilities the code can branch on.

Benchmark results on 12 held-out cases show a 4.3× speed improvement over an LLM baseline, with 93.8% accuracy when the decider answers confidently. Every recommendation requires human approval. The system is a prototype using fictional incidents and simulated resources.

---

## Concise Project Description (for the submission form, ~120 words)

**RescueFlow AI** is an emergency-response triage agent built with Strands Agents and Strands Decider 2B on AWS. It accepts free-text incident reports, collects evidence through 8 explicitly defined tools (incident lookup, risk scoring, resource status, information gap detection, cross-incident comparison), and calls Strands Decider 2B in a single forward pass to classify each incident under a written response protocol: *allow* (propose a plan), *review* (human must assess), or *block* (life-safety—escalate immediately, never auto-dispatch). A Decision Arena compares multiple incidents simultaneously and re-evaluates when conditions change—powered by the real model, not a UI trick. Benchmark: Strands Decider 2B runs 4.3× faster than Amazon Nova Pro at near-zero marginal cost, with 93.8% accuracy on confident decisions. Every recommendation requires human approval. Tags: `#strands-decider-2b` `#policy`.

---

## Five Alternative Article Titles

1. **"Triage at Scale: Using Strands Decider 2B to Classify Emergency Incidents with Calibrated Probabilities"**
   *(Emphasises the classification problem and the calibration angle.)*

2. **"RescueFlow AI: When to Escalate, When to Recommend, and When to Ask for More Information—A Strands Decider 2B Decision Pattern"**
   *(Highlights the three-way verdict structure as a reusable pattern.)*

3. **"Fast Triage, Human Control: Building an Emergency Decision Agent with Strands Decider 2B and Amazon Bedrock"**
   *(Leads with the speed/control trade-off, which is the core architectural decision.)*

4. **"Beyond If-Else: Replacing a Fixed Triage Rule Engine with a Language-Sensitive Decision Model on AWS"**
   *(Frames the project against the alternative it replaces.)*

5. **"The Policy Pattern: Classifying Decisions Before They Are Recommended, Using Strands Decider 2B"**
   *(Frames it as a contribution to reusable decision patterns, likely to interest re-users.)*

---

## Final Verification Checklist

Items marked ✅ are verified against source code, test output, or live API calls.
Items marked ⚠️ need further evidence or are explicitly labelled as planned in the article.

### Strands Decider 2B integration
- ✅ Decider called via `POST /v1/decide` with Bearer token — confirmed live
- ✅ Model `strands-decider-2B-hobson-v19` confirmed via `/v1/models` response
- ✅ Three typed questions (`priority`, `next_action`, `life_safety`) — in `agent/decision.py`
- ✅ Live decisions recorded in `submission/video/run.json` on 2026-10-22

### Benchmark numbers
- ✅ 79.2% accuracy — from `submission/bench/results.json` (12 test cases)
- ✅ 4.3× speedup at p50 — from same file
- ✅ 93.8% accuracy when confident — from same file
- ✅ $0.18 per 1,000 LLM decisions — from Nova Pro pricing in `decider_kit/llm.py`
- ⚠️ 12 cases is a small benchmark — stated clearly in the article ("directional signal, not production evaluation")

### Tests
- ✅ 78 tests pass — verified by `pytest -q` output in this session
- ✅ 28 API endpoint tests — `tests/test_rescueflow_api.py`
- ✅ 12 wiring tests — `tests/test_rescueflow_wiring.py`

### Tools
- ✅ 8 primary tools — `agent/tools.py`, names confirmed by importing TOOLS
- ✅ All tools use `@tool` decorator — verified in source

### AWS deployment
- ✅ Amazon Bedrock Nova Pro configured as LLM (`BEDROCK_MODEL_ID`) — in `.env.example`
- ✅ AgentCore CDK infrastructure prepared — `deploy/agentcore/cdk/`
- ⚠️ `./kit deploy` not yet run — stated as "planned" in the article
- ⚠️ CloudWatch logging — planned, not yet active

### Frontend
- ✅ React + Vite + Tailwind + Recharts — confirmed in `frontend/package.json`
- ✅ Frontend build exists at `frontend/dist/` — confirmed with `ls`
- ✅ Served by FastAPI when `frontend/dist/` exists — in `demo/server.py`

### Safety claims
- ✅ Human approval required — PROPOSED status, approve/reject endpoints
- ✅ No real dispatch — confirmed in agent system prompt and article
- ✅ `.env` not in repo — confirmed with `git ls-files | grep .env` (0 results)

### Statements that would benefit from more evidence
- ⚠️ "Could be applied to real decision-support workflows" — this is prospective; clearly labelled as future scope in the article.
- ⚠️ The disaster management citations (Turoff 2004, Comes 2015) are real papers but have not been accessed to verify the exact quotes used — only their topic relevance is claimed.
