import { PriorityBadge } from './PriorityBadge'
import type { Incident, Priority } from '../types'

interface Props {
  incident: Incident & { priority?: Priority }
  onSelect: (id: string) => void
  selected: boolean
}

export function IncidentRow({ incident, onSelect, selected }: Props) {
  return (
    <tr
      onClick={() => onSelect(incident.id)}
      className={`cursor-pointer hover:bg-panel transition-colors ${selected ? 'bg-panel/60' : ''}`}
    >
      <td className="py-2 px-3 font-mono text-xs text-mute">{incident.id}</td>
      <td className="py-2 px-3 font-medium capitalize">{incident.type}</td>
      <td className="py-2 px-3 text-sm text-gray-300">{incident.location}</td>
      <td className="py-2 px-3 text-sm text-gray-400">{incident.affected_people}</td>
      <td className="py-2 px-3">
        {incident.priority
          ? <PriorityBadge priority={incident.priority} />
          : <span className="text-mute text-xs">—</span>}
      </td>
      <td className="py-2 px-3">
        <span className={`text-xs px-2 py-0.5 rounded-full border ${
          incident.status === 'active'
            ? 'text-green-400 border-green-800 bg-green-950/40'
            : 'text-mute border-border'
        }`}>{incident.status}</span>
      </td>
      <td className="py-2 px-3 text-xs text-mute">{incident.report_time}</td>
    </tr>
  )
}
