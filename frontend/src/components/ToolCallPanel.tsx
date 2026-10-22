import type { ToolCall } from "../types";

const TOOL_ICONS: Record<string, string> = {
  get_incident_details: "🔍",
  list_active_incidents: "📋",
  get_resource_status: "🚒",
  calculate_preliminary_risk: "📊",
  identify_information_gaps: "⚠️",
  compare_incidents: "⚖️",
  propose_response_plan: "📝",
  save_decision_record: "💾",
};

interface Props {
  toolCalls: ToolCall[];
  deciderLatencyMs?: number | null;
}

export default function ToolCallPanel({ toolCalls, deciderLatencyMs }: Props) {
  if (!toolCalls.length) return null;

  const total = toolCalls.reduce((s, t) => s + t.latency_ms, 0);

  return (
    <div className="bg-slate-900 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-slate-300 text-sm font-semibold">Tools called ({toolCalls.length})</h3>
        <span className="text-slate-500 text-xs">{total} ms total</span>
      </div>
      <div className="space-y-1.5">
        {toolCalls.map((tc, i) => (
          <details key={i} className="group">
            <summary className="flex items-center gap-2 cursor-pointer list-none rounded px-2 py-1.5 hover:bg-slate-800 transition-colors">
              <span className="text-base">{TOOL_ICONS[tc.name] ?? "🔧"}</span>
              <span className="text-slate-300 text-sm font-medium flex-1">{tc.name}</span>
              <span className="text-slate-500 text-xs">{tc.latency_ms} ms</span>
              <span className="text-slate-600 text-xs group-open:rotate-90 transition-transform">▶</span>
            </summary>
            <div className="mt-1.5 ml-8 space-y-1.5">
              <div>
                <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Arguments</p>
                <pre className="text-xs text-slate-400 bg-slate-800 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(tc.arguments, null, 2)}
                </pre>
              </div>
              <div>
                <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Result</p>
                <pre className="text-xs text-slate-400 bg-slate-800 rounded p-2 overflow-x-auto whitespace-pre-wrap max-h-40">
                  {JSON.stringify(tc.result, null, 2)}
                </pre>
              </div>
            </div>
          </details>
        ))}
      </div>
      {deciderLatencyMs != null && (
        <p className="mt-3 text-xs text-slate-500 border-t border-slate-800 pt-2">
          Strands Decider 2B: {deciderLatencyMs} ms
        </p>
      )}
    </div>
  );
}
