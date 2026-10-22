export type Priority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NEEDS_REVIEW'
export type DecisionStatus = 'PROPOSED' | 'APPROVED' | 'REJECTED' | 'NEEDS_MORE_INFORMATION'
export type TriageVerdict = 'allow' | 'review' | 'block'

export interface Incident {
  id: string
  type: string
  location: string
  affected_people: string
  affected_people_num: number
  hazards: string
  time_sensitivity: number
  severity: number
  hazard_level: number
  report_time: string
  status: 'active' | 'resolved' | 'pending'
  report: string
  preliminary_score?: number
}

export interface Resource {
  name: string
  type: string
  count: number
  status: 'available' | 'deployed'
  suited_for: string[]
}

export interface DecisionRecord {
  id: string
  incident_id: string
  priority: Priority
  recommended_action: string
  reason_summary: string
  factors_considered: string[]
  evidence: string[]
  missing_information: string[]
  resource_recommendations: string[]
  alternatives_considered: string[]
  confidence: number
  human_review_required: boolean
  decision_status: DecisionStatus
  triage_verdict: TriageVerdict
  triage_reason: string
  tools_called: string[]
  decider_ms: number
  latency_ms: number
  created_at: string
}

export interface TriageDecision {
  pattern: string
  verdict: TriageVerdict
  priority: string
  next_action: string
  p_life_safety: number
  life_safety_p_yes: number
  priority_probs: Record<string, number>
  next_action_probs: Record<string, number>
  confident: boolean
  reason: string
  decider_ms: number
}

export interface ChatResponse {
  reply: string
  decisions: TriageDecision[]
  model_id: string
  latency_ms: number
  agent: string
  eager: boolean
  error?: string
}

export interface DashboardSummary {
  total_active: number
  critical_count: number
  high_count: number
  pending_review: number
  available_resources: number
  incidents: Incident[]
  decisions: DecisionRecord[]
}

export interface ArenaResult {
  priority_order: string[]
  reasoning: string
  trade_offs: string
  what_could_change: string
  tool_calls: string[]
  decisions: TriageDecision[]
  latency_ms: number
}
