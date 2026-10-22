import type { Incident, DecisionRecord, DashboardSummary, ChatResponse } from '../types'

const BASE = '/api'

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

// ── Incidents ────────────────────────────────────────────────────────────────

export const getIncidents = () => req<Incident[]>('/incidents')
export const getIncident = (id: string) => req<Incident>(`/incidents/${id}`)
export const createIncident = (body: Partial<Incident>) =>
  req<Incident>('/incidents', { method: 'POST', body: JSON.stringify(body) })

export const evaluateIncident = (id: string, context?: string) =>
  req<DecisionRecord>(`/incidents/${id}/evaluate`, {
    method: 'POST',
    body: JSON.stringify({ context: context || '' }),
  })

export const reassessIncident = (id: string, update: string) =>
  req<DecisionRecord>(`/incidents/${id}/reassess`, {
    method: 'POST',
    body: JSON.stringify({ update }),
  })

// ── Decisions ────────────────────────────────────────────────────────────────

export const getDecisions = () => req<DecisionRecord[]>('/decisions')
export const getDecision = (id: string) => req<DecisionRecord>(`/decisions/${id}`)
export const approveDecision = (id: string) =>
  req<DecisionRecord>(`/decisions/${id}/approve`, { method: 'POST' })
export const rejectDecision = (id: string, reason?: string) =>
  req<DecisionRecord>(`/decisions/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason || '' }),
  })

// ── Decision Arena ───────────────────────────────────────────────────────────

export const runArena = (incident_ids: string[], context?: string) =>
  req<{ reply: string; decisions: unknown[]; latency_ms: number }>('/decisions/evaluate', {
    method: 'POST',
    body: JSON.stringify({ incident_ids, context: context || '' }),
  })

// ── Dashboard ────────────────────────────────────────────────────────────────

export const getDashboard = () => req<DashboardSummary>('/dashboard/summary')

// ── Demo ─────────────────────────────────────────────────────────────────────

export const resetDemo = () =>
  req<{ ok: boolean; message: string }>('/demo/reset', { method: 'POST' })

// ── Chat (raw agent turn) ────────────────────────────────────────────────────

export const chat = (message: string, session_id = 'dashboard') =>
  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id }),
  }).then(r => r.json()) as Promise<ChatResponse>

// ── Health ───────────────────────────────────────────────────────────────────

export const getHealth = () => fetch('/health').then(r => r.json())
export const getInfo = () => fetch('/api/info').then(r => r.json())
