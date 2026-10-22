import { VerdictBadge } from './VerdictBadge'
import type { TriageDecision } from '../types'

interface Props {
  decisions: TriageDecision[]
  latency_ms?: number
}

export function DecisionPanel({ decisions, latency_ms }: Props) {
  if (decisions.length === 0) {
    return (
      <div className="card h-full flex items-center justify-center text-mute text-sm">
        Decisions appear here after the agent evaluates an incident.
      </div>
    )
  }

  return (
    <div className="card flex flex-col gap-3 overflow-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-xs uppercase tracking-widest text-mute">
          Strands Decider 2B — Triage Decisions
        </h2>
        {latency_ms && (
          <span className="text-xs font-mono text-mute">{latency_ms} ms total</span>
        )}
      </div>

      {decisions.map((d, i) => (
        <div key={i} className="bg-bg border border-border rounded-xl p-3 text-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-medium capitalize">{d.pattern || '#policy'}</span>
            <VerdictBadge verdict={d.verdict} />
          </div>

          {/* Probability bars */}
          <div className="space-y-1">
            {Object.entries(d.priority_probs ?? {}).map(([k, v]) => (
              <ProbBar key={k} label={`priority: ${k}`} p={v} />
            ))}
            {d.life_safety_p_yes !== undefined && (
              <ProbBar label="life_safety" p={d.life_safety_p_yes}
                color={d.life_safety_p_yes > 0.5 ? '#F87171' : '#34D399'} />
            )}
          </div>

          <div className="text-xs text-mute leading-relaxed">{d.reason}</div>

          <div className="flex flex-wrap gap-2 text-xs font-mono text-mute">
            <span>priority: {d.priority}</span>
            <span>·</span>
            <span>next: {d.next_action}</span>
            <span>·</span>
            <span>{d.decider_ms} ms</span>
          </div>
        </div>
      ))}

      <p className="text-xs text-mute text-center pt-1">
        Built with the AWS User Group Madurai Strands Decider hackathon kit
      </p>
    </div>
  )
}

function ProbBar({ label, p, color }: { label: string; p: number; color?: string }) {
  const fill = color ?? (p >= 0.5 ? '#34D399' : '#F87171')
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className="w-36 text-mute truncate">{label}</span>
      <div className="flex-1 h-2 bg-border rounded-full overflow-hidden">
        <div style={{ width: `${p * 100}%`, background: fill }} className="h-full rounded-full" />
      </div>
      <span className="w-8 text-right text-mute">{p.toFixed(2)}</span>
    </div>
  )
}
