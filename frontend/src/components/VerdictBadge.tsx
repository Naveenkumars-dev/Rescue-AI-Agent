import type { TriageVerdict } from '../types'

const LABELS: Record<TriageVerdict, string> = {
  allow: '✓ ALLOW',
  review: '⚠ REVIEW',
  block: '✕ BLOCK / ESCALATE',
}

export function VerdictBadge({ verdict }: { verdict: TriageVerdict }) {
  return (
    <span className={`verdict-${verdict} text-xs font-mono px-2 py-0.5 rounded-full border`}>
      {LABELS[verdict] ?? verdict}
    </span>
  )
}
