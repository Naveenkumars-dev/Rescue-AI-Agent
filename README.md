# RescueFlow AI

**An agent that decides what needs attention first.**

RescueFlow AI is an emergency-response decision-support prototype that accepts incident reports,
evaluates their severity, compares competing incidents, identifies missing information, and
recommends response priorities — using **Strands Decider 2B** as the central triage decision model
and **Amazon Bedrock** for the conversational and tool-use part.

> **This is a simulation prototype.** It does not dispatch real emergency services, contact real
> people, or take any real-world action. Simulated resources and fictional incidents only.

Built with the **AWS User Group Madurai Strands Decider hackathon kit** for the
[Agent Experience Hackathon: Strands Decider](https://builder.aws.com/build/hackathons)
(October 16–23, 2026).

---

## Why this project / problem statement

During a disaster, emergency coordinators receive many incident reports at once. Deciding which
situation needs attention first requires reading language (not just comparing numbers), assessing
uncertainty, and explaining trade-offs. A hardcoded rules engine cannot do this. A plain
chatbot does not return structured, auditable decisions.

RescueFlow AI shows how a **decision model** — Strands Decider 2B — can fill that gap: it reads
the incident report and the facts gathered by tools and returns calibrated probabilities that code
can branch on, fast and cheaply, without a full generative model per decision.

---

## Why Strands Decider 2B is central

The agent gathers facts with its tools (preliminary risk score, resource status, active incident
list, information gaps). **After** the tools run, Strands Decider 2B reads the assembled state and
answers three typed questions:

| Question | Type | What it classifies |
|---|---|---|
| `priority` | score | triage level: low / medium / high / critical |
| `next_action` | choice | recommend plan / request info / monitor / escalate |
| `life_safety` | noul | immediate or probable threat to life? (P 0–1) |

The arithmetic (the preliminary score, the ranking) stays in code. The model reads the prose:
what the report says, whether it signals a threat to life, what to do next.

The verdict is always one of:
- **allow** — clear, non-life-threatening: propose a response plan for human approval.
- **review** — missing information, borderline, or low confidence: hold for a human coordinator.
- **block** — life-safety incident: escalate to professional emergency services immediately.

One forward pass per incident. The probabilities and the verdict appear in the live decision panel.

### Decision pattern tag
`#policy` — an emergency-response triage policy gate, from `decider_kit/patterns/policy.py`.

---

## Architecture

```
User / Browser
     │
     ▼
React dashboard (Vite + TypeScript + Tailwind)     [frontend/]
     │  http://localhost:3000  (proxies /api → :8501)
     ▼
FastAPI demo server                                 [demo/server.py]
  ├── GET  /health
  ├── GET  /api/incidents
  ├── POST /api/incidents
  ├── GET  /api/incidents/{id}
  ├── POST /api/incidents/{id}/evaluate
  ├── POST /api/incidents/{id}/reassess
  ├── GET  /api/decisions
  ├── GET  /api/decisions/{id}
  ├── POST /api/decisions/evaluate        (Decision Arena)
  ├── POST /api/decisions/{id}/approve
  ├── POST /api/decisions/{id}/reject
  ├── GET  /api/dashboard/summary
  ├── POST /api/demo/reset
  └── POST /api/chat
     │
     ▼
HackathonAgent  [agent/agent.py]
  ├── Strands Agent  ──► Amazon Bedrock (Nova Pro) | Ollama (local)
  │     └── 13 tools  [agent/tools.py]
  └── TriagePolicy   ──► Strands Decider 2B  [agent/decision.py]
         │
         └── .env: DECIDER_MODE=local | ugmdu | custom
```

**AWS deployment (via `./kit deploy`):**
```
Amazon Bedrock AgentCore Runtime   (the deployed agent)
     │
     ▼  AGENTCORE_ARN in .env
FastAPI demo server (same server.py, DEMO_TARGET=agentcore)
     │
     ▼
React dashboard (same build, served by the demo server)
```

---

## Verified, working functionality

| Feature | Status |
|---|---|
| 78 automated tests (agent tools, wiring, all 12 API endpoints) | ✅ passing |
| RescueFlow triage decision pattern (`#policy`, typed questions) | ✅ complete |
| 13 agent tools (8 primary + 5 backward-compat) | ✅ complete |
| All 12 required API endpoints | ✅ complete |
| Decision Arena (compare 3 incidents + Change Conditions) | ✅ complete |
| React dashboard (Vite + Tailwind + Recharts) | ✅ builds cleanly |
| 26 labelled eval cases (13 tune / 13 test) | ✅ complete |
| Demo server serves React build when `frontend/dist` exists | ✅ complete |
| Fallback to kit chat UI when React build is absent | ✅ complete |

### Needs AWS / model credentials to run end-to-end

| Feature | What is needed |
|---|---|
| Full chat / evaluation | `./kit setup` (choose LLM provider + decider mode) |
| `./kit bench` (accuracy vs LLM baseline) | Strands Decider 2B server or hosted key |
| `./kit deploy` (AgentCore Runtime) | AWS account + Bedrock model access |
| `./kit video`, `./kit article`, `./kit publish` | AWS, GitHub, deployment done first |

---

## Quick start (local, offline)

```bash
# 1. venv and deps (already done if you ran ./kit venv)
./kit venv          # creates .venv and installs strands-agents, fastapi, etc.

# 2. Copy and fill in .env
cp .env.example .env
# Edit .env: set DECIDER_MODE, LLM_PROVIDER and credentials

# 3. Start the demo server (serves the React dashboard + all API endpoints)
./kit demo          # or: .venv/bin/python -m uvicorn demo.server:app --port 8501 --reload

# 4. Open the dashboard
open http://localhost:8501

# 5. Start the React dev server (hot-reload, optional)
cd frontend && npm run dev   # http://localhost:3000 (proxies API to :8501)
```

---

## Setup options (choose one)

### Option A — Fully local (no cloud cost)

```bash
# Install Ollama
brew install ollama          # macOS
# Linux: curl -fsSL https://ollama.com/install.sh | sh

# Pull a model (4 GB, Apple silicon or 8 GB+ RAM)
ollama pull qwen3.5:4b

# Start Ollama (in a separate terminal)
ollama serve

# Start the Strands Decider server (in another terminal)
./kit serve

# Configure
./kit setup --llm local --mode local
# .env will be written with LLM_PROVIDER=local, DECIDER_MODE=local

./kit run    # smoke test one scripted conversation
```

### Option B — Amazon Bedrock + hosted decider

```bash
# Configure AWS credentials (opens a terminal prompt — never paste in chat)
./kit aws-login

# Configure the agent
./kit setup --llm bedrock --mode ugmdu
# .env: LLM_PROVIDER=bedrock, DECIDER_MODE=ugmdu, DECIDER_API_KEY=<your key>

./kit run    # verify end-to-end
```

### Option C — Bedrock + local decider

```bash
./kit aws-login
./kit serve         # local Strands Decider on :8099
./kit setup --llm bedrock --mode local
./kit run
```

---

## Environment variables (.env)

| Variable | Purpose | Default |
|---|---|---|
| `LLM_PROVIDER` | `bedrock` / `local` / `ugmdu` | `bedrock` |
| `DECIDER_MODE` | `local` / `ugmdu` / `custom` | `ugmdu` |
| `DECIDER_URL` | decider endpoint | hosted URL |
| `DECIDER_API_KEY` | decider API key | — |
| `BEDROCK_MODEL_ID` | the agent's LLM | `us.amazon.nova-pro-v1:0` |
| `AWS_REGION` | AWS region | `us-east-1` |

---

## Run tests

```bash
./kit test                          # 78 tests: agent, tools, wiring, all API endpoints
.venv/bin/python -m pytest -q       # same, direct
```

---

## Benchmark (needs model access)

```bash
./kit bench --split test            # decider vs Bedrock LLM on 13 held-out cases
# Results in submission/bench/results.json and results.md
```

---

## Deploy to AWS

```bash
./kit deploy                        # AgentCore Runtime; writes submission/deployment.json
./kit invoke "Flood at Riverside"   # test the deployed agent
# Frontend: serve frontend/dist from S3 + CloudFront, or from the demo server
./kit destroy                       # remove the AgentCore Runtime when done
```

**Required IAM permissions:**
- `bedrock:InvokeModel` on the selected Bedrock model
- `bedrock-agentcore:CreateAgentRuntime`, `InvokeAgentRuntime`, `DeleteAgentRuntime`
- `logs:CreateLogGroup`, `logs:PutLogEvents` (CloudWatch)

**Estimated cost (demo scenario, 100 evaluations):**
- Bedrock Nova Pro: ~$0.10 (input) + $0.40 (output) = ~$0.50
- Strands Decider (hosted): ~$0.004 (100 × $0.035/1,000)
- AgentCore Runtime: ~$0.01/hour idle

---

## The Decision Arena — judging highlight

Submit three fictional incidents. The agent:
1. Calls its tools for each incident (risk score, resources, comparisons)
2. Strands Decider 2B classifies each one (priority, next action, life-safety)
3. Explains the priority order, trade-offs, and what could change the recommendation
4. When you click **Change Conditions** ("resident confirmed trapped"), the agent re-evaluates
   using the real model — the verdict and explanation update in front of you

This is the core demonstration: the decision changes because the evidence changes, not because
the UI rearranges fixed rules.

---

## Sample decision trace (from the kit's offline demo)

```
INC-001  FLOOD — Riverside
  preliminary score: 80
  VERDICT: BLOCK  priority=critical  next_action=escalate_to_human  p_life_safety=0.92
  reason: Life-safety incident detected. Escalate to professional emergency services.

INC-002  ROAD OBSTRUCTION — Oak Lane
  preliminary score: 27
  VERDICT: ALLOW  priority=low  next_action=recommend_response_plan  p_life_safety=0.08
  reason: Clear, non-life-threatening and actionable. Propose a response plan.

INC-003  POWER OUTAGE — Market Square
  preliminary score: 26
  VERDICT: ALLOW  priority=low  next_action=monitor  p_life_safety=0.08
  reason: No response action needed yet. Monitor and re-evaluate.
```

---

## Repository structure

```
agent/
  AGENT.md           use-case description
  decision.py        #policy triage pattern (QUESTIONS, build_state, TriagePolicy)
  tools.py           13 tools (8 primary + 5 aliases)
  agent.py           HackathonAgent (chat contract, TriagePolicy wired post-draft)
  eval_cases.jsonl   26 labelled cases (13 tune / 13 test)
  demo_script.yaml   4 demo turns
  data/              incidents.json (10 seed incidents), resources.json (8 resource types)
decider_kit/         reusable library (AWS User Group Madurai)
demo/
  server.py          FastAPI server (12 API endpoints + chat)
  static/            kit chat UI fallback
frontend/
  src/               React + TypeScript + Tailwind dashboard
  dist/              built output (served by demo server)
tests/
  test_agent_contract.py        kit contract tests
  test_rescueflow_wiring.py     12 wiring tests (FakeDecider)
  test_rescueflow_api.py        28 API endpoint tests
  test_bench_and_checks.py      kit bench + check tests
  fakes.py                      FakeDecider
.kiro/specs/rescueflow-ai/      requirements, design, tasks
.env.example
```

---

## Security and limitations

- All incident reports are treated as untrusted input; prompt injection attempts in the `report` field do not affect system instructions.
- The prototype never dispatches real resources, contacts real people, or acts without human approval.
- Confidence values are indicative — not statistically calibrated probabilities.
- AWS credentials stay in `.env` (git-ignored) or IAM roles. Never commit `.env`.
- `./kit check` and `./kit publish` scan for secrets before publishing.

---

## Submission tags

`#strands-decider-2b`  `#policy`

---

Built with the **AWS User Group Madurai** Strands Decider hackathon kit.
