import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import type { DeciderEvidence } from "../types";

const PRIORITY_COLORS: Record<string, string> = {
  low: "#22c55e",
  medium: "#eab308",
  high: "#f97316",
  critical: "#ef4444",
};

const ACTION_COLORS: Record<string, string> = {
  recommend_response_plan: "#3b82f6",
  request_missing_information: "#8b5cf6",
  monitor: "#22c55e",
  escalate_to_human: "#ef4444",
};

interface Props {
  evidence: DeciderEvidence;
}

export default function DeciderEvidencePanel({ evidence }: Props) {
  const priorityData = Object.entries(evidence.priority_probabilities).map(([k, v]) => ({
    name: k.charAt(0).toUpperCase() + k.slice(1),
    prob: Math.round(v * 100),
    key: k,
  }));

  const actionData = Object.entries(evidence.next_action_probabilities).map(([k, v]) => ({
    name: k.replace(/_/g, " "),
    prob: Math.round(v * 100),
    key: k,
  }));

  const lifeSafety = evidence.life_safety_p_yes ?? 0;

  return (
    <div className="bg-slate-900 rounded-xl p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">
          Strands Decider 2B — raw evidence
        </h3>
        {evidence.decider_latency_ms != null && (
          <span className="text-xs text-slate-500">{evidence.decider_latency_ms} ms</span>
        )}
      </div>

      {/* Priority probabilities */}
      {priorityData.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">Priority probabilities</p>
          <ResponsiveContainer width="100%" height={90}>
            <BarChart data={priorityData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <YAxis tick={{ fontSize: 10, fill: "#64748b" }} domain={[0, 100]} />
              <Tooltip
                formatter={(v: number) => [`${v}%`, "Probability"]}
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 6, fontSize: 12 }}
              />
              <Bar dataKey="prob" radius={[4, 4, 0, 0]}>
                {priorityData.map((entry, i) => (
                  <Cell key={i} fill={PRIORITY_COLORS[entry.key] ?? "#64748b"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Life-safety P(yes) */}
      <div>
        <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">Life-safety signal P(yes)</p>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-3 rounded-full bg-slate-700 overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.round(lifeSafety * 100)}%`,
                background: lifeSafety >= 0.6 ? "#ef4444" : lifeSafety >= 0.4 ? "#f97316" : "#22c55e",
              }}
            />
          </div>
          <span className="text-sm font-mono text-slate-300 w-12 text-right">
            {(lifeSafety * 100).toFixed(1)}%
          </span>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          ≥60% → escalate (block) · 40–60% → uncertain (review) · &lt;40% → continue
        </p>
      </div>

      {/* Next-action probabilities */}
      {actionData.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">
            Next-action: <span className="text-slate-300 capitalize">{evidence.next_action?.replace(/_/g, " ")}</span>
          </p>
          <div className="space-y-1.5">
            {actionData.map((d) => (
              <div key={d.key} className="flex items-center gap-2">
                <span className="text-xs text-slate-400 w-44 shrink-0 truncate">{d.name}</span>
                <div className="flex-1 h-2 rounded-full bg-slate-700 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${d.prob}%`, background: ACTION_COLORS[d.key] ?? "#64748b" }}
                  />
                </div>
                <span className="text-xs font-mono text-slate-400 w-10 text-right">{d.prob}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
