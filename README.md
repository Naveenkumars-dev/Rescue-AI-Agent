# RescueFlow AI 🌊

> **An agent that decides what needs attention first.**

A decision-support prototype for emergency coordinators. Multiple disaster incidents compete for
limited simulated resources. The agent evaluates them, compares severity and urgency, identifies
missing information, and recommends a priority order — explained and auditable.

Built for the **[Agent Experience Hackathon: Strands Decider](https://builder.aws.com/build/hackathons/4f50957c-1d08-37ab-b11c-97516b9adeb4/agent-experience-hackathon-strands-decider)**
(16–23 October 2026).

**Built with the AWS User Group Madurai Strands Decider hackathon kit.**

---

## How Strands Decider 2B participates

This project implements the **`#policy`** reusable decision pattern. Before RescueFlow shows
any recommendation for an incident, Strands Decider 2B (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`)
classifies it under a written emergency-response protocol with three typed questions:

| Question | Type | Options |
|---|---|---|
| `priority` | score | low / medium / high / critical |
| `next_action` | choice | recommend_response_plan / request_missing_information / monitor / escalate_to_human |
| `life_safety` | noul (yes/no) | Is this an immediate threat to life? |

The decider returns **calibrated probabilities** in one forward pass. The code in
`backend/app/agents/decision.py` turns those probabilities into an `allow / review / block`
verdict using explicit thresholds (life_safety P(yes) ≥ 0.6 → block; ≥ 0.4 → review; etc.).

Every number (the preliminary risk score, the incident ranking) is computed by the tools in code
and placed in the state as a fact. **The decider reads language and makes the judgement; it does
not do arithmetic.**

The generative part (drafting the recommendation text) runs through the Strands Agents SDK on
Amazon Bedrock (Amazon Nova Pro by default).

---

## Architecture

```
Browser (React + Vite + Tailwind)
    │
    │  HTTP / JSON
    ▼
FastAPI backend  (port 8000)
    │
    ├── Orchestrator
    │     1. get_incident_details
    │     2. list_active_incidents
    │     3. calculate_preliminary_risk   ← arithmetic in code → placed in state
    │     4. get_resource_status
    │     5. identify_information_gaps
    │     6. draft_recommendation         ← Strands Agent → Amazon Bedrock (or template)
    │     7. build_state + triage         ← Strands Decider 2B (or labelled simulation)
    │     8. propose_response_plan
    │     9. save_decision_record
    │
    ├── decider_kit/                      ← official AWS UG Madurai kit (Apache-2.0)
    │     client.py    one client for local / hosted Strands Decider
    │     llm.py       Strands Agents SDK model factory
    │     config.py    settings from .env
    │     patterns/    five labelled reusable decision patterns
    │
    └── In-memory store (reseeds from JSON on demo reset)

AWS (production):
    Amazon ECS/Fargate  ← backend container
    Amazon S3 + CloudFront ← frontend static assets
    Amazon Bedrock ← Strands Agent LLM
    Strands Decider 2B ← via UG Madurai hosted API or local serve
    Amazon DynamoDB ← persistent decision records (optional; store.py provides the interface)
    Amazon CloudWatch ← logs
```

---

## Two modes

| Mode | What runs | How to enable |
|---|---|---|
| **Live** | Real Strands Decider 2B + Strands Agent on Bedrock | Set `DECIDER_API_KEY` and AWS credentials (see `.env.example`) |
| **Demo** | All tools run; decision is a clearly-labelled deterministic fallback | Default — no credentials needed |

The mode banner at the top of every page shows which is active. Every decision record carries
`live_decider: bool` and `mode: "live" | "demo"` so nothing is ever falsely presented as
coming from the real model.

---

## Running locally

### 1. Backend (demo mode — no credentials needed)

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=..:. uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

### 3. Enable live Strands Decider 2B

```bash
cp .env.example .env
# Fill in DECIDER_API_KEY (from https://www.awsugmdu.in)
# Fill in AWS credentials for Bedrock (BEDROCK_MODEL_ID, AWS_REGION)
```

Then restart the backend. The mode banner turns green.

---

## Backend tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -v
# 55 unit tests, 1 live integration test (skipped unless DECIDER_API_KEY is set)
```

Live integration test (real model):
```bash
# After setting DECIDER_API_KEY in .env:
.venv/bin/python -m pytest tests/test_live_integration.py -rA
```

---

## Decision Arena demo script (3 minutes)

1. Open http://localhost:5173 → **Decision Arena ⚔️**
2. The three demo incidents are pre-selected (INC-001 flood, INC-002 road, INC-003 power).
3. Click **Run Arena** → watch the agent call 7 tools per incident, build the state, run the decider, and produce a ranked list.
4. Observe: INC-001 (flood, trapped residents) → CRITICAL / block · INC-002 (road) → LOW / allow · INC-003 (power) → LOW / review
5. Click **"Confirmed trapped resident"** → the agent re-evaluates with worsened conditions.
6. Show the before/after ranking comparison — the decision changed because new evidence changed the state the decider read.
7. Switch to **Tools Called** tab → show every real tool call (no fabrication).
8. Switch to **Decider Evidence** tab (live mode) → show the raw probability bars from Strands Decider 2B.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health + mode |
| GET | `/api/info` | Mode info, model IDs |
| GET | `/api/incidents` | List incidents |
| POST | `/api/incidents` | Create incident |
| GET | `/api/incidents/{id}` | Get incident |
| POST | `/api/decisions/evaluate` | Run agent on an incident |
| POST | `/api/incidents/{id}/reassess` | Change conditions + re-evaluate |
| GET | `/api/decisions` | List all decisions |
| GET | `/api/decisions/{id}` | Get a decision |
| POST | `/api/decisions/{id}/approve` | Human approval |
| POST | `/api/decisions/{id}/reject` | Human rejection |
| POST | `/api/arena/evaluate` | Decision Arena (2+ incidents) |
| POST | `/api/arena/reassess` | Arena + change conditions (before/after) |
| GET | `/api/dashboard/summary` | Dashboard stats |
| GET | `/api/activity` | Agent activity timeline |
| POST | `/api/demo/reset` | Reset to seed data |

---

## Tested functionality ✅

- Incident creation and validation (Pydantic, 422 on bad input)
- All 8 agent tools: get_incident_details, list_active_incidents, get_resource_status, calculate_preliminary_risk, identify_information_gaps, compare_incidents, propose_response_plan, save_decision_record
- The reusable `#policy` decision pattern: all allow/review/block branches
- Strands Decider 2B live path (fake decider drives priority in tests)
- Simulated fallback (clearly labelled, non-calibrated confidence)
- Competing incident evaluation (Decision Arena)
- Reassessment when conditions change (decision priority shifts)
- Decision history, approval, rejection
- Demo reset
- Safety constraints (life-safety → block → human review required)
- Model errors fall back gracefully to simulated mode

## Planned / not yet in this build

- Amazon DynamoDB persistence (in-memory store provided; DynamoDB interface documented)
- AWS CDK/CloudFormation deployment scripts
- `./kit bench` latency/cost comparison vs a Bedrock LLM
- Demo video recording
- AWS Builder Center article draft

---

## Reusable decision pattern — `#policy`

See `backend/app/agents/decision.py`. Copy the file, rewrite `PROTOCOL` and the three typed
questions for your safety-critical domain, and keep the `allow/review/block` thresholds in
`decide()`. The rule: compute every number in a tool, place the result in the state, let the
decider read language, not do arithmetic.

**Tags:** `#strands-decider-2b` `#policy`

---

## Credits

- **decider_kit** library: [AWS User Group Madurai](https://www.awsugmdu.in) — Apache-2.0
- Strands Decider 2B: [strands-labs/strands-decider](https://github.com/strands-labs/strands-decider) — Apache-2.0
- Strands Agents SDK: Apache-2.0
- This is not an official AWS project.
# Rescue-AI-Agent
