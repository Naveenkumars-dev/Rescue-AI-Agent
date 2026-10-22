import { useEffect, useState, useCallback } from 'react'
import { StatCard } from '../components/StatCard'
import { IncidentRow } from '../components/IncidentRow'
import { DecisionPanel } from '../components/DecisionPanel'
import { ToolTimeline } from '../components/ToolTimeline'
import { IncidentForm } from '../components/IncidentForm'
import { ResourceChart } from '../components/ResourceChart'
import { DecisionArena } from '../components/DecisionArena'
import * as api from '../services/api'
import type { Incident, DecisionRecord, TriageDecision } from '../types'

interface Resource { name: string; count: number; status: string }

export function Dashboard() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [decisions, setDecisions] = useState<DecisionRecord[]>([])
  const [resources] = useState<Resource[]>([
    { name: 'Swift-water Boat', count: 2, status: 'available' },
    { name: 'Ambulance', count: 5, status: 'available' },
    { name: 'Fire Engine', count: 3, status: 'available' },
    { name: 'Hazmat Team', count: 1, status: 'available' },
    { name: 'Road Crew', count: 4, status: 'available' },
    { name: 'Search & Rescue', count: 1, status: 'deployed' },
  ])
  const [selected, setSelected] = useState<string | null>(null)
  const [liveDecisions, setLiveDecisions] = useState<TriageDecision[]>([])
  const [toolCalls, setToolCalls] = useState<Record<string, unknown>[]>([])
  const [evaluating, setEvaluating] = useState(false)
  const [resetLoading, setResetLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'incidents' | 'arena' | 'history'>('incidents')
  const [agentInfo, setAgentInfo] = useState<{ agent: string; llm: string; decider: string } | null>(null)
  const [evalError, setEvalError] = useState('')

  const load = useCallback(async () => {
    try {
      const [incs, decs] = await Promise.all([api.getIncidents(), api.getDecisions()])
      setIncidents(incs)
      setDecisions(decs)
    } catch {
      // If custom API not available, silently show empty state
    }
  }, [])

  useEffect(() => {
    load()
    api.getInfo().then(setAgentInfo).catch(() => {})
  }, [load])

  const evaluate = async (id: string) => {
    if (evaluating) return
    setEvaluating(true)
    setEvalError('')
    setLiveDecisions([])
    setToolCalls([])
    try {
      // Use the chat API for live evaluation
      const msg = `Evaluate incident ${id} and recommend a response. Call all necessary tools to gather facts.`
      const result = await api.chat(msg, `eval-${id}-${Date.now()}`)
      if (result.error) throw new Error(result.error)
      setLiveDecisions(result.decisions)
      setSelected(id)
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : 'Evaluation failed')
    } finally {
      setEvaluating(false)
    }
  }

  const reset = async () => {
    setResetLoading(true)
    try {
      await api.resetDemo()
      // Reset agent
      await fetch('/api/reset', { method: 'POST' })
      await load()
      setSelected(null)
      setLiveDecisions([])
      setToolCalls([])
      setEvalError('')
    } catch {
      // demo endpoint may not exist in kit; reload anyway
      window.location.reload()
    } finally {
      setResetLoading(false)
    }
  }

  const critical = incidents.filter(i => i.status === 'active' && i.severity >= 5).length
  const active = incidents.filter(i => i.status === 'active').length
  const pending = decisions.filter(d => d.decision_status === 'PROPOSED').length
  const availRes = resources.filter(r => r.status === 'available').reduce((a, r) => a + r.count, 0)

  const selectedIncident = incidents.find(i => i.id === selected)

  return (
    <div className="min-h-screen bg-bg text-gray-100 font-sans">
      {/* Header */}
      <header className="border-b border-border px-6 py-3 flex items-center gap-3">
        <div className="w-2.5 h-2.5 rounded-full bg-brand shadow-[0_0_12px_#FF9900]" />
        <h1 className="font-bold text-lg">RescueFlow AI</h1>
        <span className="text-mute text-sm">— Emergency Response Decision Support</span>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs bg-yellow-900/40 border border-yellow-700 text-yellow-400 px-2 py-0.5 rounded">
            SIMULATION — prototype only
          </span>
          {agentInfo && (
            <span className="text-xs text-mute font-mono">
              {agentInfo.llm} · decider: {agentInfo.decider}
            </span>
          )}
          <button
            onClick={reset}
            disabled={resetLoading}
            className="btn-ghost text-sm"
          >
            {resetLoading ? 'Resetting…' : '↺ Reset Demo'}
          </button>
        </div>
      </header>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 px-6 py-4">
        <StatCard label="Active Incidents" value={active} color="text-brand" />
        <StatCard label="Critical / High" value={critical}
          color="text-red-400" sub="life-safety events" />
        <StatCard label="Pending Review" value={pending}
          color="text-yellow-400" sub="awaiting human approval" />
        <StatCard label="Available Resources" value={availRes}
          color="text-green-400" sub="simulated units" />
      </div>

      {/* Tab bar */}
      <div className="px-6 flex gap-1 border-b border-border">
        {(['incidents', 'arena', 'history'] as const).map(t => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === t
                ? 'border-brand text-brand'
                : 'border-transparent text-mute hover:text-gray-300'
            }`}
          >
            {t === 'incidents' ? 'Incidents' : t === 'arena' ? '⚔ Decision Arena' : 'Decision History'}
          </button>
        ))}
      </div>

      {/* Main content */}
      <div className="px-6 py-4">

        {/* Incidents tab */}
        {activeTab === 'incidents' && (
          <div className="grid grid-cols-3 gap-4">
            {/* Left: incident list + form */}
            <div className="col-span-2 space-y-4">
              {/* Resources chart */}
              <div className="card">
                <p className="text-xs text-mute uppercase tracking-widest mb-2">
                  Simulated Resources (demo data)
                </p>
                <ResourceChart resources={resources} />
              </div>

              {/* Incident table */}
              <div className="card overflow-auto">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs text-mute uppercase tracking-widest">Active Incidents</p>
                  <span className="text-xs text-mute">{active} active</span>
                </div>
                {incidents.length === 0 ? (
                  <p className="text-mute text-sm text-center py-6">
                    No incidents loaded. Click Reset Demo or submit one below.
                  </p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-mute text-xs border-b border-border">
                        <th className="pb-2 px-3">ID</th>
                        <th className="pb-2 px-3">Type</th>
                        <th className="pb-2 px-3">Location</th>
                        <th className="pb-2 px-3">Affected</th>
                        <th className="pb-2 px-3">Priority</th>
                        <th className="pb-2 px-3">Status</th>
                        <th className="pb-2 px-3">Reported</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {incidents.map(i => (
                        <IncidentRow
                          key={i.id}
                          incident={i}
                          onSelect={evaluate}
                          selected={selected === i.id}
                        />
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Submit form */}
              <div className="card">
                <p className="text-xs text-mute uppercase tracking-widest mb-3">Submit New Incident</p>
                <IncidentForm onCreated={load} />
              </div>
            </div>

            {/* Right: decision + tools */}
            <div className="space-y-4">
              {selectedIncident && (
                <div className="card">
                  <p className="text-xs text-mute uppercase tracking-widest mb-2">Incident Report</p>
                  <p className="text-sm font-medium capitalize">{selectedIncident.type} — {selectedIncident.location}</p>
                  <p className="text-xs text-mute mt-1 leading-relaxed">{selectedIncident.report}</p>
                  <div className="mt-2 flex gap-2 text-xs text-mute font-mono">
                    <span>hazards: {selectedIncident.hazards}</span>
                  </div>
                  <button
                    onClick={() => evaluate(selectedIncident.id)}
                    disabled={evaluating}
                    className="btn-primary w-full mt-3 text-sm"
                  >
                    {evaluating ? 'Evaluating…' : '▶ Evaluate this incident'}
                  </button>
                </div>
              )}

              {evalError && (
                <div className="bg-red-950/40 border border-red-800 rounded-lg p-3 text-red-400 text-xs">
                  {evalError.includes('credentials') || evalError.includes('Credentials')
                    ? 'AWS credentials not configured. See setup instructions below.'
                    : evalError}
                </div>
              )}

              <DecisionPanel decisions={liveDecisions} />

              {toolCalls.length > 0 && (
                <div className="card">
                  <p className="text-xs text-mute uppercase tracking-widest mb-3">
                    Tools Called
                  </p>
                  <ToolTimeline tools={toolCalls as never} />
                </div>
              )}

              {liveDecisions.length === 0 && !evaluating && (
                <div className="card text-center py-8 text-mute text-sm">
                  <p>Click an incident row or "Evaluate" to run the agent.</p>
                  <p className="text-xs mt-2">
                    Requires AWS Bedrock credentials or a local Ollama model.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Decision Arena tab */}
        {activeTab === 'arena' && <DecisionArena />}

        {/* History tab */}
        {activeTab === 'history' && (
          <div className="card">
            <p className="text-xs text-mute uppercase tracking-widest mb-3">Decision History</p>
            {decisions.length === 0 ? (
              <p className="text-mute text-sm text-center py-8">
                No decisions recorded yet. Evaluate an incident to start.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-mute text-xs border-b border-border">
                    <th className="pb-2 px-3">Incident</th>
                    <th className="pb-2 px-3">Priority</th>
                    <th className="pb-2 px-3">Status</th>
                    <th className="pb-2 px-3">Summary</th>
                    <th className="pb-2 px-3">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {decisions.map((d, i) => (
                    <tr key={i}>
                      <td className="py-2 px-3 font-mono text-xs">{d.incident_id}</td>
                      <td className="py-2 px-3 text-xs">{d.priority ?? '—'}</td>
                      <td className="py-2 px-3 text-xs">{d.decision_status}</td>
                      <td className="py-2 px-3 text-xs text-mute truncate max-w-xs">
                        {d.reason_summary || d.recommended_action}
                      </td>
                      <td className="py-2 px-3 text-xs text-mute">{d.created_at ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="px-6 py-3 border-t border-border text-center text-xs text-mute">
        Built with the AWS User Group Madurai Strands Decider hackathon kit ·
        RescueFlow AI is a prototype — not for real emergency dispatch
      </footer>
    </div>
  )
}
