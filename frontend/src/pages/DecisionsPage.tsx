import { useEffect, useState, useCallback } from "react";
import { listDecisions, approveDecision, rejectDecision } from "../services/api";

const PRIORITY_COLOR: Record<string, string> = {
  CRITICAL: "#ef4444", HIGH: "#f97316", MEDIUM: "#eab308", LOW: "#22c55e", NEEDS_REVIEW: "#64748b",
};
const TRIAGE_ICON: Record<string, string> = { block: "🔴", review: "🟡", allow: "🟢" };
const STATUS_STYLE: Record<string, string> = {
  PROPOSED: "text-blue-400 border-blue-500/30 bg-blue-500/10",
  APPROVED: "text-green-400 border-green-500/30 bg-green-500/10",
  REJECTED: "text-red-400 border-red-500/30 bg-red-500/10",
  NEEDS_MORE_INFORMATION: "text-purple-400 border-purple-500/30 bg-purple-500/10",
};

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("ALL");
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    listDecisions()
      .then(d => setDecisions([...d].reverse()))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleApprove = async (id: string) => {
    await approveDecision(id, "").catch(e => setError(e.message));
    refresh();
  };
  const handleReject = async (id: string) => {
    await rejectDecision(id, "").catch(e => setError(e.message));
    refresh();
  };

  const statuses = ["ALL", "PROPOSED", "APPROVED", "REJECTED", "NEEDS_MORE_INFORMATION"];
  const filtered = filter === "ALL" ? decisions : decisions.filter(d => d.decision_status === filter);

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="h-[calc(100vh-57px)] overflow-y-auto p-5 space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Decision History</h1>
          <p className="text-xs text-slate-500 mt-0.5">{decisions.length} total decisions</p>
        </div>
        <div className="flex gap-1">
          {statuses.map(s => (
            <button key={s} onClick={() => setFilter(s)}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
                filter === s
                  ? "border-blue-500/50 bg-blue-500/15 text-blue-300"
                  : "border-slate-700/50 text-slate-500 hover:text-slate-300 hover:border-slate-600"
              }`}>
              {s === "NEEDS_MORE_INFORMATION" ? "NEEDS INFO" : s}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-slate-600 gap-3">
          <span className="text-4xl">📋</span>
          <p>No decisions yet. Evaluate some incidents first.</p>
        </div>
      )}

      <div className="space-y-3">
        {filtered.map(d => {
          const priority = d.priority as string;
          const status = d.decision_status as string;
          const triage = d.triage_action as string;
          const pColor = PRIORITY_COLOR[priority] ?? "#64748b";
          const sStyle = STATUS_STYLE[status] ?? "text-slate-400 border-slate-500/30 bg-slate-500/10";

          return (
            <div key={d.decision_id as string}
              className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4 fade-in-up">

              {/* Top row */}
              <div className="flex flex-wrap items-center gap-3 mb-3">
                <span className="font-mono text-xs text-slate-600">{d.decision_id as string}</span>
                <span className="font-semibold text-white">{d.incident_id as string}</span>
                <span className="text-xs font-bold font-mono px-2 py-0.5 rounded border"
                  style={{ color: pColor, borderColor: pColor + "40", background: pColor + "15" }}>
                  {priority}
                </span>
                <span className="text-sm">{TRIAGE_ICON[triage] ?? "⚪"} <span className="text-xs text-slate-400">{triage?.toUpperCase()}</span></span>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded border font-mono ${sStyle}`}>
                  {status?.replace(/_/g, " ")}
                </span>
                {!d.live_decider && (
                  <span className="text-[10px] text-amber-400 bg-amber-900/20 border border-amber-600/20 px-2 py-0.5 rounded font-mono">
                    SIMULATED
                  </span>
                )}

                {/* Approve/reject */}
                {status === "PROPOSED" && (
                  <div className="ml-auto flex gap-2">
                    <button onClick={() => handleApprove(d.decision_id as string)}
                      className="text-xs px-3 py-1.5 rounded-lg bg-green-600/20 border border-green-500/30 text-green-400 hover:bg-green-600/30 transition-colors font-medium">
                      ✓ Approve
                    </button>
                    <button onClick={() => handleReject(d.decision_id as string)}
                      className="text-xs px-3 py-1.5 rounded-lg bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-600/30 transition-colors font-medium">
                      ✗ Reject
                    </button>
                  </div>
                )}
              </div>

              {/* Reason */}
              <p className="text-sm text-slate-300 mb-2 leading-relaxed">{d.reason_summary as string}</p>

              {/* Missing info */}
              {Array.isArray(d.missing_information) && (d.missing_information as string[]).length > 0 && (
                <p className="text-xs text-amber-400 mb-2">
                  ⚠ Missing: {(d.missing_information as string[]).join(" · ")}
                </p>
              )}

              {/* Meta */}
              <div className="flex flex-wrap gap-4 text-[10px] text-slate-600 font-mono border-t border-slate-800/60 pt-2 mt-2">
                <span>score {d.preliminary_score as number}/100</span>
                <span>confidence {((d.confidence as number) * 100).toFixed(0)}%</span>
                {d.recorded_at != null && <span>{String(d.recorded_at)}</span>}
                {d.reviewed_at != null && <span>reviewed {String(d.reviewed_at)}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
