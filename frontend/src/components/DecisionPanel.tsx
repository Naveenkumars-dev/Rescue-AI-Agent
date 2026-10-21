import { useState } from "react";
import type { DecisionResponse } from "../types";
import { PriorityBadge, StatusBadge, TriageBadge, ModeBadge } from "./Badge";
import ToolCallPanel from "./ToolCallPanel";
import DeciderEvidencePanel from "./DeciderEvidencePanel";

interface Props {
  result: DecisionResponse;
  onApprove?: (id: string, note: string) => void;
  onReject?: (id: string, note: string) => void;
  showActions?: boolean;
}

export default function DecisionPanel({ result, onApprove, onReject, showActions = true }: Props) {
  const [note, setNote] = useState("");
  const d = result.decision;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-slate-500 text-sm font-medium">{result.decision_id}</span>
              <ModeBadge mode={d.mode} live={d.live_decider && d.live_llm} />
              {!d.live_decider && (
                <span className="text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                  SIMULATED DECISION
                </span>
              )}
            </div>
            <h2 className="text-lg font-bold text-slate-900">Incident {d.incident_id}</h2>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <PriorityBadge priority={d.priority} />
            <TriageBadge action={d.triage_action} />
            <StatusBadge status={d.decision_status} />
          </div>
        </div>

        {/* Reason */}
        <div className="bg-slate-50 rounded-lg p-3 mb-4">
          <p className="text-sm font-medium text-slate-700 mb-1">Decision reason</p>
          <p className="text-sm text-slate-600">{d.reason_summary}</p>
        </div>

        {/* Recommended action */}
        <div className="mb-4">
          <p className="text-sm font-medium text-slate-700 mb-1">Recommended action</p>
          <p className="text-sm text-slate-600">{d.recommended_action}</p>
        </div>

        {d.response_plan && (
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 mb-4">
            <p className="text-sm font-semibold text-blue-900 mb-1">Response plan</p>
            <p className="text-sm text-blue-800">{d.response_plan}</p>
            {d.human_review_required && (
              <p className="text-xs text-blue-600 mt-1">⚠ Human coordinator approval required before action.</p>
            )}
          </div>
        )}

        {/* Score + confidence */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-slate-50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-slate-800">{d.preliminary_score ?? "—"}</div>
            <div className="text-xs text-slate-500 mt-0.5">Preliminary risk score /100</div>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-slate-800">{(d.confidence * 100).toFixed(0)}%</div>
            <div className="text-xs text-slate-500 mt-0.5">
              {d.live_decider ? "Decider confidence" : "Heuristic marker (not calibrated)"}
            </div>
          </div>
        </div>

        {/* Lists */}
        <ListSection title="Factors considered" items={d.factors_considered} icon="🔎" />
        <ListSection title="Evidence" items={d.evidence} icon="📌" />
        {d.missing_information.length > 0 && (
          <ListSection title="Missing information" items={d.missing_information} icon="❓"
            className="border-t border-amber-100 pt-3 mt-3" textColor="text-amber-700" />
        )}
        {d.resource_recommendations.length > 0 && (
          <ListSection title="Resource recommendations" items={d.resource_recommendations} icon="🚒" />
        )}
        {d.alternatives_considered.length > 0 && (
          <ListSection title="Competing incidents considered" items={d.alternatives_considered} icon="⚖️" />
        )}

        {/* Approval controls */}
        {showActions && d.decision_status === "PROPOSED" && onApprove && onReject && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <p className="text-sm font-medium text-slate-700 mb-2">Human review</p>
            <input
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Reviewer note (optional)"
              value={note}
              onChange={e => setNote(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                onClick={() => onApprove(result.decision_id, note)}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg py-2 transition-colors"
              >
                ✓ Approve
              </button>
              <button
                onClick={() => onReject(result.decision_id, note)}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg py-2 transition-colors"
              >
                ✗ Reject
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Decider evidence */}
      {d.live_decider && d.decider_evidence && (
        <DeciderEvidencePanel evidence={d.decider_evidence} />
      )}

      {/* Tool calls */}
      <ToolCallPanel
        toolCalls={result.tool_calls}
        deciderLatencyMs={d.decider_evidence?.decider_latency_ms}
      />

      <div className="text-xs text-slate-400 text-right">
        Latency: {result.latency_ms} ms · Model: {result.model_id}
      </div>
    </div>
  );
}

function ListSection({
  title, items, icon, className = "", textColor = "text-slate-600",
}: {
  title: string; items: string[]; icon: string; className?: string; textColor?: string;
}) {
  if (!items.length) return null;
  return (
    <div className={`mt-3 ${className}`}>
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">{icon} {title}</p>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className={`text-sm ${textColor} flex gap-2`}>
            <span className="text-slate-400 shrink-0">·</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
