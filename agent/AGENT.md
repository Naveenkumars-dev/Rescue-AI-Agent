# Use case

RescueFlow AI — an emergency-response decision-support agent. It triages incident reports,
prioritizes competing incidents, recommends response actions, and decides when a human coordinator
must step in before anything is recommended. These answers drive the code, benchmark, README,
article and video.

- **Pitch:** an emergency-response triage agent that reads incident reports, decides which need
  attention first, and never auto-recommends a response for a life-safety incident.
- **Who it is for:** emergency-response coordinators who triage many incoming reports at once and
  need a clear priority, a recommended action, and a flag for what needs human verification.
- **Features:**
  - accepts incident reports in plain language and triages them;
  - a transparent preliminary priority score is computed in code, and the cross-incident ranking too;
  - Strands Decider 2B classifies each incident under a response protocol: allow / review / block;
  - life-safety incidents are escalated and never auto-recommended or auto-dispatched;
  - a live decision panel in the demo UI shows the triage verdict and its probabilities;
  - deployed on Amazon Bedrock AgentCore Runtime.
- **The decision handed to Strands Decider 2B:** before a response recommendation is shown, is the
  incident clear, non-life-threatening and actionable, or must it be held / escalated under the
  response protocol? (`#policy`)
- **Why a decision model:** the triage judgement needs reading language (whether a report describes
  a threat to life, what to do next, how urgent it is), runs on every incident, and must return a
  confidence the code can branch on; the arithmetic (the score, the ranking) stays in code.
- **Amazon Bedrock:** the conversation, fact extraction and tool use (Amazon Nova Pro by default).

This agent is a decision-support prototype. It never dispatches real emergency services, contacts
real people, or acts without a human approving a recommendation. It uses simulated resources.

Built with the AWS User Group Madurai Strands Decider hackathon kit.
