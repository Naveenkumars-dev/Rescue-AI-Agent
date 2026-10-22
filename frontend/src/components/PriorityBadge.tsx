import type { Priority } from '../types'

export function PriorityBadge({ priority }: { priority: Priority }) {
  const key = priority?.toLowerCase() ?? 'needs_review'
  return (
    <span className={`badge-${key} text-xs font-mono px-2 py-0.5 rounded-full border`}>
      {priority}
    </span>
  )
}
