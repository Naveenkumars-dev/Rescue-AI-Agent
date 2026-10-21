import type { IncidentOut } from "../types";

const TYPE_ICONS: Record<string, string> = {
  flood: "🌊",
  fire: "🔥",
  "road obstruction": "🚧",
  "power outage": "⚡",
  "gas leak": "💨",
  medical: "🏥",
  earthquake: "🌍",
  tornado: "🌪️",
  "chemical spill": "☣️",
};

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? "bg-red-500" : score >= 60 ? "bg-orange-500" : score >= 35 ? "bg-yellow-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-500 w-6 text-right">{score}</span>
    </div>
  );
}

interface Props {
  incident: IncidentOut;
  selected?: boolean;
  onClick?: () => void;
  onEvaluate?: () => void;
  loading?: boolean;
}

export default function IncidentCard({ incident, selected, onClick, onEvaluate, loading }: Props) {
  const icon = TYPE_ICONS[incident.type.toLowerCase()] ?? "🚨";
  const isActive = incident.status === "active";

  return (
    <div
      className={`rounded-xl border bg-white shadow-sm transition-all cursor-pointer ${
        selected ? "border-brand-500 ring-2 ring-brand-200" : "border-slate-200 hover:border-slate-300"
      }`}
      onClick={onClick}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <span className="text-xl">{icon}</span>
            <div>
              <p className="text-xs text-slate-400 font-mono">{incident.id}</p>
              <p className="text-sm font-semibold text-slate-800 capitalize">{incident.type}</p>
            </div>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            isActive ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"
          }`}>
            {incident.status}
          </span>
        </div>

        <p className="text-xs text-slate-500 mb-1">📍 {incident.location}</p>
        <p className="text-xs text-slate-500 mb-2">👥 {incident.affected_people}</p>

        {incident.preliminary_score != null && (
          <div className="mb-3">
            <p className="text-xs text-slate-400 mb-1">Risk score</p>
            <ScoreBar score={incident.preliminary_score} />
          </div>
        )}

        <div className="flex gap-3 text-xs text-slate-500">
          <span title="Severity">⚠ {incident.severity}/5</span>
          <span title="Time sensitivity">⏱ {incident.time_sensitivity}/5</span>
          <span title="Hazard level">🔥 {incident.hazard_level}/5</span>
        </div>

        <p className="text-xs text-slate-400 mt-2 line-clamp-2">{incident.report}</p>
      </div>

      {onEvaluate && (
        <div className="px-4 pb-3">
          <button
            onClick={e => { e.stopPropagation(); onEvaluate(); }}
            disabled={loading}
            className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg py-1.5 transition-colors"
          >
            {loading ? "Evaluating…" : "Evaluate →"}
          </button>
        </div>
      )}
    </div>
  );
}
