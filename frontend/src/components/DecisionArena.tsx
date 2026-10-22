import { useState } from 'react'
import { chat } from '../services/api'
import { DecisionPanel } from './DecisionPanel'
import type { TriageDecision } from '../types'

const SEED_INCIDENTS = [
  {
    id: 'INC-001',
    label: 'Flood — Riverside (may be trapped)',
    report: 'INC-001: Flood warning for the low-lying Riverside residential area. Water is rising rapidly and some residents may be trapped.',
  },
  {
    id: 'INC-002',
    label: 'Road obstruction — Oak Lane',
    report: 'INC-002: A tree branch is blocking one lane of Oak Lane. No injuries and traffic is slow.',
  },
  {
    id: 'INC-003',
    label: 'Power outage — Market Square',
    report: 'INC-003: Power outage at Market Square commercial area. No immediate hazard and duration is unknown.',
  },
]

const CHANGE_CONDITIONS = [
  'A resident is now confirmed trapped in a first-floor apartment in the Riverside flood zone.',
  'The road obstruction at Oak Lane now blocks both lanes, cutting off emergency access to Riverside.',
  'The power outage has spread to a medical facility that relies on powered equipment.',
  'Swift-water rescue boats are no longer available — the team has been redeployed.',
  'Flood water at Riverside is receding. No more trapped residents reported.',
]

interface ArenaRun {
  label: string
  reply: string
  decisions: TriageDecision[]
  latency_ms: number
}

export function DecisionArena() {
  const [selected, setSelected] = useState<string[]>(['INC-001', 'INC-002', 'INC-003'])
  const [condition, setCondition] = useState('')
  const [customCondition, setCustomCondition] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [runs, setRuns] = useState<ArenaRun[]>([])

  const toggle = (id: string) => {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])
  }

  const run = async (changeLabel?: string) => {
    if (selected.length < 2) return
    setLoading(true)
    setError('')
    const isChange = !!changeLabel
    const incidents = SEED_INCIDENTS.filter(i => selected.includes(i.id))
    const msg = isChange
      ? `CONDITION CHANGE: ${changeLabel}\n\nRe-evaluate these incidents in light of this change:\n${incidents.map(i => i.report).join('\n')}\nCompare all three, recommend a priority order with reasons, and explain what changed.`
      : `Decision Arena: compare these incidents and recommend a priority order with clear reasoning:\n${incidents.map(i => i.report).join('\n')}\nList the competing risks, trade-offs, key uncertainties, and what new information could change your recommendation.`
    try {
      const result = await chat(msg, `arena-${Date.now()}`)
      if (result.error) throw new Error(result.error)
      setRuns(r => [{
        label: isChange ? `After: ${changeLabel}` : 'Initial assessment',
        reply: result.reply,
        decisions: result.decisions,
        latency_ms: result.latency_ms,
      }, ...r].slice(0, 6))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Evaluation failed')
    } finally {
      setLoading(false)
    }
  }

  const changeConditionText = customCondition || condition

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-bold text-lg">Decision Arena</h2>
          <p className="text-mute text-sm mt-0.5">
            Compare competing incidents. Change conditions and see how the agent reassesses.
          </p>
        </div>
        <span className="text-xs bg-panel border border-border px-2 py-1 rounded text-mute">
          SIMULATION — not real dispatch
        </span>
      </div>

      {/* Incident selection */}
      <div className="card space-y-2">
        <p className="text-xs text-mute uppercase tracking-widest">Select incidents to compare</p>
        <div className="flex flex-wrap gap-2">
          {SEED_INCIDENTS.map(i => (
            <button
              key={i.id}
              onClick={() => toggle(i.id)}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                selected.includes(i.id)
                  ? 'bg-brand/20 border-brand text-brand'
                  : 'border-border text-mute hover:border-gray-500'
              }`}
            >
              {i.label}
            </button>
          ))}
        </div>
      </div>

      {/* Run arena */}
      <button
        className="btn-primary w-full"
        onClick={() => run()}
        disabled={loading || selected.length < 2}
      >
        {loading ? 'Agent is evaluating…' : '▶ Run Decision Arena'}
      </button>

      {/* Change Conditions */}
      {runs.length > 0 && (
        <div className="card space-y-3">
          <p className="text-xs text-mute uppercase tracking-widest">Change Conditions</p>
          <p className="text-xs text-gray-400">
            Simulate new information. The agent will re-evaluate using the real model.
          </p>
          <div className="flex flex-wrap gap-2">
            {CHANGE_CONDITIONS.map(c => (
              <button
                key={c}
                onClick={() => { setCondition(c); setCustomCondition('') }}
                className={`text-xs px-2 py-1 rounded border transition-colors text-left ${
                  condition === c && !customCondition
                    ? 'bg-yellow-900/30 border-yellow-700 text-yellow-400'
                    : 'border-border text-mute hover:border-gray-500'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
          <textarea
            className="input-field text-xs resize-none"
            rows={2}
            placeholder="Or type a custom condition change…"
            value={customCondition}
            onChange={e => { setCustomCondition(e.target.value); setCondition('') }}
          />
          <button
            className="btn-ghost w-full"
            onClick={() => run(changeConditionText)}
            disabled={loading || !changeConditionText.trim()}
          >
            {loading ? 'Re-evaluating…' : '↺ Reassess with Changed Conditions'}
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-950/40 border border-red-800 rounded-lg p-3 text-red-400 text-sm">
          {error.includes('credentials') || error.includes('Credentials')
            ? 'AWS credentials not configured. Run ./kit setup --llm bedrock to configure Amazon Bedrock, or ./kit setup --llm local for Ollama.'
            : error}
        </div>
      )}

      {/* Results */}
      {runs.map((run, i) => (
        <div key={i} className={`space-y-3 ${i > 0 ? 'opacity-70' : ''}`}>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${i === 0 ? 'bg-brand' : 'bg-border'}`} />
            <span className="text-sm font-medium">{run.label}</span>
            <span className="text-xs text-mute ml-auto">{run.latency_ms} ms</span>
          </div>
          <div className="card">
            <pre className="whitespace-pre-wrap text-sm text-gray-200 leading-relaxed font-sans">
              {run.reply}
            </pre>
          </div>
          {run.decisions.length > 0 && (
            <DecisionPanel decisions={run.decisions} latency_ms={run.latency_ms} />
          )}
          {i < runs.length - 1 && (
            <div className="border-t border-border my-2" />
          )}
        </div>
      ))}
    </div>
  )
}
