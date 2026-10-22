import type { ActivityEvent } from "../types";

const EVENT_ICONS: Record<string, string> = {
  incident_created: "📥",
  incident_evaluated: "🤖",
  arena_evaluated: "⚔️",
  conditions_changed: "🔄",
  decision_saved: "💾",
  decision_approved: "✅",
  decision_rejected: "❌",
};

const EVENT_COLORS: Record<string, string> = {
  incident_created: "bg-blue-100 text-blue-700",
  incident_evaluated: "bg-purple-100 text-purple-700",
  arena_evaluated: "bg-indigo-100 text-indigo-700",
  conditions_changed: "bg-amber-100 text-amber-700",
  decision_saved: "bg-slate-100 text-slate-600",
  decision_approved: "bg-green-100 text-green-700",
  decision_rejected: "bg-red-100 text-red-700",
};

interface Props {
  events: ActivityEvent[];
}

export default function ActivityTimeline({ events }: Props) {
  const reversed = [...events].reverse();

  if (!reversed.length) {
    return (
      <div className="text-center py-8 text-slate-400 text-sm">
        No activity yet — evaluate an incident to see it here.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {reversed.map((ev, i) => {
        const icon = EVENT_ICONS[ev.event] ?? "📌";
        const color = EVENT_COLORS[ev.event] ?? "bg-slate-100 text-slate-600";
        return (
          <div key={i} className="flex items-start gap-3">
            <div className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm ${color}`}>
              {icon}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-slate-700 font-medium">
                {ev.event.replace(/_/g, " ")}
                {ev.incident_id && <span className="text-slate-500 font-normal"> · {ev.incident_id}</span>}
                {ev.decision_id && <span className="text-slate-500 font-normal"> · {ev.decision_id}</span>}
              </p>
              {ev.priority && (
                <p className="text-xs text-slate-500">priority: {ev.priority}</p>
              )}
              <p className="text-xs text-slate-400">{ev.at}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
