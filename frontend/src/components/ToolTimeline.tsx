interface ToolCall {
  stage: string
  [key: string]: unknown
}

interface Props {
  tools: ToolCall[]
}

const ICONS: Record<string, string> = {
  get_incident_details: '🔍',
  list_active_incidents: '📋',
  get_resource_status: '🚒',
  check_resource_availability: '🚒',
  calculate_preliminary_risk: '📊',
  estimate_response_priority: '📊',
  identify_information_gaps: '❓',
  request_missing_information: '❓',
  compare_incidents: '⚖️',
  propose_response_plan: '📝',
  recommend_response_plan: '📝',
  save_decision_record: '💾',
  record_decision: '💾',
}

export function ToolTimeline({ tools }: Props) {
  if (tools.length === 0) {
    return (
      <p className="text-mute text-xs text-center py-4">
        Tool calls appear here after an evaluation.
      </p>
    )
  }

  return (
    <div className="relative">
      <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />
      <div className="space-y-3">
        {tools.map((t, i) => (
          <div key={i} className="flex gap-3 relative">
            <div className="w-8 h-8 flex-shrink-0 flex items-center justify-center
                            bg-panel border border-border rounded-full z-10 text-base">
              {ICONS[t.stage] ?? '⚙️'}
            </div>
            <div className="flex-1 min-w-0 bg-bg border border-border rounded-lg p-2 text-xs">
              <p className="font-mono font-medium text-gray-300">{t.stage}</p>
              {t.incident_id != null && <p className="text-mute">incident: {String(t.incident_id)}</p>}
              {typeof t.preliminary_score === 'number' && (
                <p className="text-brand">score: {String(t.preliminary_score)}</p>
              )}
              {typeof t.resources_summary === 'string' && (
                <p className="text-mute truncate">{t.resources_summary}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
