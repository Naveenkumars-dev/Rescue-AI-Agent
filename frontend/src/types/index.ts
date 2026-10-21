// API types that mirror the backend Pydantic schemas

export type Priority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "NEEDS_REVIEW";
export type DecisionStatus = "PROPOSED" | "APPROVED" | "REJECTED" | "NEEDS_MORE_INFORMATION";
export type TriageAction = "allow" | "review" | "block";

export interface IncidentOut {
  id: string;
  type: string;
  location: string;
  affected_people: string;
  affected_people_num: number;
  hazards: string;
  time_sensitivity: number;
  severity: number;
  hazard_level: number;
  report_time: string;
  status: string;
  report: string;
  preliminary_score: number | null;
}

export interface IncidentCreate {
  type: string;
  location: string;
  report: string;
  severity: number;
  time_sensitivity: number;
  affected_people_num: number;
  hazard_level: number;
  hazards: string;
}

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
  latency_ms: number;
}

export interface DeciderEvidence {
  priority_probabilities: Record<string, number>;
  next_action: string | null;
  next_action_probabilities: Record<string, number>;
  life_safety_p_yes: number | null;
  triage_action: string | null;
  decider_latency_ms: number | null;
}

export interface StructuredDecision {
  incident_id: string;
  priority: Priority;
  recommended_action: string;
  reason_summary: string;
  factors_considered: string[];
  evidence: string[];
  missing_information: string[];
  resource_recommendations: string[];
  alternatives_considered: string[];
  confidence: number;
  human_review_required: boolean;
  decision_status: DecisionStatus;
  response_plan: string | null;
  preliminary_score: number | null;
  triage_action: TriageAction;
  live_decider: boolean;
  live_llm: boolean;
  mode: string;
  decider_evidence: DeciderEvidence | null;
}

export interface DecisionResponse {
  decision_id: string;
  decision: StructuredDecision;
  tool_calls: ToolCall[];
  model_id: string;
  latency_ms: number;
  mode: string;
}

export interface ArenaRanking {
  rank: number;
  incident_id: string;
  incident_type: string;
  location: string;
  priority: Priority;
  priority_rank: number;
  preliminary_score: number;
  triage_action: TriageAction;
  recommended_action: string;
  human_review_required: boolean;
  reason: string;
  decision_id: string;
}

export interface ArenaResponse {
  ranking: ArenaRanking[];
  explanation: string;
  trade_offs: string[];
  unresolved_uncertainties: string[];
  what_could_change_it: string[];
  comparison: Record<string, unknown>;
  tool_calls: ToolCall[];
  decisions: DecisionResponse[];
  mode: string;
  model_id: string;
  latency_ms: number;
}

export interface ArenaReassessResponse {
  before: ArenaResponse;
  after: ArenaResponse;
  change_applied: Record<string, unknown>;
  note: string;
}

export interface ReassessResponse {
  incident_id: string;
  before: DecisionResponse;
  after: DecisionResponse;
  change_applied: Record<string, unknown>;
  note: string;
}

export interface DashboardSummary {
  active_incidents: number;
  critical_count: number;
  high_count: number;
  pending_human_review: number;
  total_decisions: number;
  proposed: number;
  approved: number;
  rejected: number;
  needs_more_information: number;
  resources: Resource[];
  mode: string;
}

export interface Resource {
  name: string;
  type: string;
  count: number;
  status: string;
  suited_for: string[];
}

export interface ModeInfo {
  mode: string;
  decider_live: boolean;
  decider_mode: string;
  decider_model: string;
  llm_live: boolean;
  llm_provider: string;
  llm_model_id: string;
  reason: string;
  agent_name: string;
  kit_credit: string;
  checked_at: string;
}

export interface ActivityEvent {
  event: string;
  at: string;
  incident_id?: string;
  decision_id?: string;
  priority?: string;
  mode?: string;
  [key: string]: unknown;
}
