# References

All sources below are verifiable and directly relevant to the implementation.
Citations are provided by section of use.

---

## Strands Decider 2B

1. **Strands Decider — Official Repository**  
   https://github.com/strands-labs/strands-decider  
   Source code, model cards, serving instructions (Apache-2.0 licence).

2. **Introducing Strands Decider — Official Blog Post**  
   https://strandsagents.com/blog/introducing-strands-decider/  
   Describes the model's design: typed questions (noul, choice, score), calibrated probabilities, one forward pass per decision.

3. **Strands Decider 2B (Qwen3.5-based) — Model Card**  
   `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` on Hugging Face.  
   Apache-2.0. Used via the AWS User Group Madurai hosted API.

4. **Strands Decider 2B (Hobson-based) — Model Card**  
   `StrandsAgents/strands-decider-2B-hobson-v19` on Hugging Face.  
   The model served by the hosted API during development (confirmed via `/v1/models`).

---

## Strands Agents SDK

5. **Strands Agents SDK — Official Documentation**  
   https://strandsagents.com/latest/  
   Agent, tool, InterventionHandler, and model provider APIs used in `agent/agent.py` and `agent/decision.py`.

6. **Strands Agents SDK — PyPI**  
   https://pypi.org/project/strands-agents/  
   Version 1.61.1 installed in `.venv`. Apache-2.0.

---

## Amazon Web Services

7. **Amazon Bedrock — Overview**  
   https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html  
   Generative model backend. Model: `us.amazon.nova-pro-v1:0` (Nova Pro).

8. **Amazon Bedrock AgentCore Runtime**  
   https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html  
   Target deployment platform via `./kit deploy` (planned; not yet completed).

9. **Amazon Nova Pro — Model Documentation**  
   https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html  
   Default LLM used by the agent (`BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0`).

---

## Hackathon Kit

10. **Agent Experience Hackathon: Strands Decider — Official Rules**  
    https://builder.aws.com/build/hackathons/4f50957c-1d08-37ab-b11c-97516b9adeb4/agent-experience-hackathon-strands-decider  
    Submission requirements, judging criteria, eligibility (16–23 October 2026).

11. **AWS User Group Madurai Strands Decider Hackathon Kit**  
    https://github.com/Vivek0712/decider-hackathon-kit  
    `decider_kit/` reusable library used in this project. Apache-2.0.  
    Includes: `Decider` client, five labelled decision patterns, benchmark (`decider_kit/bench.py`), LLM helpers, AgentCore glue.

---

## Disaster Management and Decision Support (Background)

12. **Turoff, M., Chumer, M., Van de Walle, B., & Yao, X. (2004)**  
    *The Design of a Dynamic Emergency Response Management Information System (DERMIS).*  
    Journal of Information Technology Theory and Application, 5(4), 1–35.  
    Foundational work on real-time information management during emergencies.

13. **Comes, T., Vybornova, O., & Van de Walle, B. (2015)**  
    *Bringing Structure to the Disaster Data Typhoon: An Analysis of Decision-Making Needs in the Response to Haiyan.*  
    Proceedings of ISCRAM 2015.  
    Discusses triage decision support and information gaps in disaster response.

14. **FastAPI — Official Documentation**  
    https://fastapi.tiangolo.com/  
    Backend framework. Version ≥0.115.

15. **React — Official Documentation**  
    https://react.dev/  
    Frontend framework. Version 18.3.1.

16. **Vite — Official Documentation**  
    https://vitejs.dev/  
    Frontend build tool. Version 5.3.4.

17. **Pydantic — Official Documentation**  
    https://docs.pydantic.dev/  
    Request/response validation. Version 2.x.

---

*All URLs verified as of October 2026. No citations, authors, dates, or results have been fabricated.  
Bench numbers (79.2% accuracy, 4.3× speedup, $0.1785 per 1,000 LLM decisions) come from  
`submission/bench/results.json`, run on 12 labelled test cases using the hosted Strands Decider 2B  
API and Amazon Nova Pro as the LLM baseline.*
