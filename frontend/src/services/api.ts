import type {
  ActivityEvent,
  ArenaReassessResponse,
  ArenaResponse,
  DashboardSummary,
  DecisionResponse,
  IncidentCreate,
  IncidentOut,
  ModeInfo,
  ReassessResponse,
} from "../types";

const BASE: string = import.meta.env.VITE_API_BASE ?? "";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// --- health / info ---
export const getHealth = () => req<{ status: string; mode: string; decider_live: boolean; llm_live: boolean }>("/health");
export const getInfo = () => req<ModeInfo>("/api/info");

// --- incidents ---
export const getIncidents = (status?: string) =>
  req<IncidentOut[]>("/api/incidents" + (status ? `?status=${status}` : ""));
export const getIncident = (id: string) => req<IncidentOut>(`/api/incidents/${id}`);
export const createIncident = (data: IncidentCreate) =>
  req<IncidentOut>("/api/incidents", { method: "POST", body: JSON.stringify(data) });

// --- decisions ---
export const evaluateDecision = (incident_id: string) =>
  req<DecisionResponse>("/api/decisions/evaluate", {
    method: "POST",
    body: JSON.stringify({ incident_id }),
  });

export const reassessIncident = (incident_id: string, changes: Record<string, unknown>, note = "") =>
  req<ReassessResponse>(`/api/incidents/${incident_id}/reassess`, {
    method: "POST",
    body: JSON.stringify({ changes, note }),
  });

export const getDecision = (id: string) => req<Record<string, unknown>>(`/api/decisions/${id}`);
export const listDecisions = (incident_id?: string) =>
  req<Record<string, unknown>[]>("/api/decisions" + (incident_id ? `?incident_id=${incident_id}` : ""));
export const approveDecision = (id: string, reviewer_note = "") =>
  req<{ decision_id: string; decision_status: string }>(`/api/decisions/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ reviewer_note }),
  });
export const rejectDecision = (id: string, reviewer_note = "") =>
  req<{ decision_id: string; decision_status: string }>(`/api/decisions/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reviewer_note }),
  });

// --- arena ---
export const evaluateArena = (incident_ids: string[]) =>
  req<ArenaResponse>("/api/arena/evaluate", {
    method: "POST",
    body: JSON.stringify({ incident_ids }),
  });

export const reassessArena = (
  incident_ids: string[],
  incident_id: string,
  changes: Record<string, unknown>,
  note = ""
) =>
  req<ArenaReassessResponse>("/api/arena/reassess", {
    method: "POST",
    body: JSON.stringify({
      incident_ids,
      change: { incident_id, changes, note },
    }),
  });

// --- dashboard ---
export const getDashboardSummary = () => req<DashboardSummary>("/api/dashboard/summary");

// --- activity ---
export const getActivity = (limit = 50) =>
  req<{ activity: ActivityEvent[] }>(`/api/activity?limit=${limit}`);

// --- demo ---
export const resetDemo = () => req<{ ok: boolean; message: string }>("/api/demo/reset", { method: "POST" });
