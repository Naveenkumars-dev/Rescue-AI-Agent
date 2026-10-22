import { useEffect, useState } from "react";
import { getIncidents, reassessArena } from "../services/api";
import type { IncidentOut, ArenaResponse, ArenaReassessResponse } from "../types";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
} from "recharts";

const DEMO_IDS = ["INC-001", "INC-002", "INC-003"];

const SCENARIOS = [
  {
    label: "Trapped resident confirmed",
    incident_id: "INC-001",
    changes: { severity: 5, hazard_level: 5, affected_people_num: 6, affected_people: "6 residents confirmed trapped" },
    note: "6 residents confirmed trapped as water level rises.",
    icon: "🌊",
  },
  {
    label: "Road blocks emergency access",
    incident_id: "INC-002",
    changes: { severity: 4, hazard_level: 4, affected_people_num: 3, affected_people: "3 vehicles trapped" },
    note: "Road block now trapping 3 vehicles including a medical emergency.",
    icon: "🚧",
  },
  {
    label: "Power outage hits hospital",
    incident_id: "INC-003",
    changes: { severity: 5, hazard_level: 5, affected_people_num: 120, affected_people: "~120 hospital patients" },
    note: "Power outage now affecting local hospital with 120 patients.",
    icon: "⚡",
  },
];

const PRIORITY_COLOR: Record<string, string> = {
  CRITICAL: "#ef4444", HIGH: "#f97316", MEDIUM: "#eab308", LOW: "#22c55e", NEEDS_REVIEW: "#64748b",
};
const TRIAGE_ICON: Record<string, string> = { block: "🔴", review: "🟡", allow: "🟢" };

export default function ArenaPage() {
  const [incidents, setIncidents] = useState<IncidentOut[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set(DEMO_IDS));
  const [arena, setArena] = useState<ArenaResponse | null>(null);
  const [reassess, setReassess] = useState<ArenaReassessResponse | null>(null);
  const [streamSteps, setStreamSteps] = useState<{ icon: string; tool: string; inc: string; msg: string }[]>([]);
  const [running, setRunning] = useState(false);
  const [reassessing, setReassessing] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"rank" | "compare" | "evidence">("rank");

  useEffect(() => {
    getIncidents().then(d => setIncidents(d.filter(i => i.status === "active"))).catch(() => null);
  }, []);

  const toggle = (id: string) => setSelected(p => {
    const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n;
  });

  const runArena = async () => {
    if (selected.size < 2) return setError("Select at least 2 incidents.");
    setRunning(true); setArena(null); setReassess(null); setError(""); setStreamSteps([]);

    const ids = Array.from(selected);
    const steps: typeof streamSteps = [];

    try {
      const es = new EventSource(`http://127.0.0.1:8000/api/arena/stream`, { });
      // SSE with POST via fetch-event-source workaround — use fetch+ReadableStream
      es.close();

      // Use the streaming POST endpoint
      const resp = await fetch("http://127.0.0.1:8000/api/arena/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_ids: ids }),
      });

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));

          if (data.type === "tool") {
            const step = { icon: data.icon, tool: data.tool, inc: data.incident_id, msg: data.message };
            steps.push(step);
            setStreamSteps([...steps]);
          }
          if (data.type === "evaluating") {
            const step = { icon: "🔄", tool: "evaluating", inc: data.incident_id, msg: `Evaluating ${data.incident_id} (${data.incident_type})…` };
            steps.push(step);
            setStreamSteps([...steps]);
          }
          if (data.type === "ranking") {
            steps.push({ icon: "⚖️", tool: "ranking", inc: "", msg: "Ranking by priority…" });
            setStreamSteps([...steps]);
          }
          if (data.type === "complete") {
            setArena(data.result);
            setStreamSteps(steps.map(s => ({ ...s, done: true } as typeof s)));
          }
          if (data.type === "error") setError(data.message);
        }
      }
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const runReassess = async (scenario: typeof SCENARIOS[0]) => {
    if (!arena) return;
    setReassessing(true); setError("");
    try {
      const r = await reassessArena(Array.from(selected), scenario.incident_id, scenario.changes, scenario.note);
      setReassess(r); setArena(r.after);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setReassessing(false);
    }
  };

  const activeInc = incidents;

  // Radar data for comparison
  const radarData = arena ? arena.ranking.map(r => ({
    incident: r.incident_id,
    score: r.preliminary_score,
    priority: (["LOW","MEDIUM","HIGH","CRITICAL"].indexOf(r.priority) + 1) * 25,
  })) : [];

  return (
    <div className="h-[calc(100vh-57px)] overflow-y-auto p-5 space-y-5">

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          ⚔️ Decision Arena
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          The agent evaluates competing incidents, ranks them, explains the priority order, then updates when conditions change.
        </p>
      </div>

      {/* Selector + run */}
      <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Select incidents (min 2)</p>
          <div className="flex gap-2">
            <button onClick={() => setSelected(new Set(DEMO_IDS))}
              className="text-xs px-3 py-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors">
              Demo set
            </button>
            <button onClick={runArena} disabled={running || selected.size < 2}
              className="text-sm px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-bold transition-all">
              {running ? (
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin" />
                  Running…
                </span>
              ) : `▶ Run Arena (${selected.size})`}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {activeInc.slice(0, 10).map(inc => (
            <button key={inc.id} onClick={() => toggle(inc.id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all ${
                selected.has(inc.id)
                  ? "border-blue-500/60 bg-blue-500/15 text-blue-300"
                  : "border-slate-700/60 text-slate-500 hover:border-slate-500 hover:text-slate-300"
              }`}>
              <div className={`w-3 h-3 rounded border flex items-center justify-center ${selected.has(inc.id) ? "bg-blue-500 border-blue-500" : "border-slate-600"}`}>
                {selected.has(inc.id) && <span className="text-white text-[8px]">✓</span>}
              </div>
              <span className="font-mono text-[10px] opacity-60">{inc.id}</span>
              <span className="capitalize">{inc.type}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-3 text-sm text-red-300 flex justify-between">
          {error} <button onClick={() => setError("")} className="text-red-500">✕</button>
        </div>
      )}

      {/* Live stream panel */}
      {(running || streamSteps.length > 0) && !arena && (
        <div className="bg-slate-900/60 border border-blue-500/20 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            {running && <div className="w-3 h-3 border border-blue-400 border-t-transparent rounded-full animate-spin" />}
            <p className="text-xs font-semibold text-blue-400 uppercase tracking-widest">
              {running ? "Agent executing…" : "Execution complete"}
            </p>
          </div>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {streamSteps.map((s, i) => (
              <div key={i} className="flex items-center gap-2.5 text-xs fade-in-up">
                <span className="w-5 text-center shrink-0">{s.icon}</span>
                {s.inc && <span className="font-mono text-[10px] text-slate-600 shrink-0">{s.inc}</span>}
                <span className="font-mono text-blue-400/80 shrink-0">{s.tool}</span>
                <span className="text-slate-400">{s.msg}</span>
              </div>
            ))}
            {running && (
              <div className="flex gap-1 pl-7 pt-1">
                {[0,1,2].map(i => <div key={i} className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: `${i*0.15}s` }} />)}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Results */}
      {arena && (
        <div className="space-y-4">

          {/* Tab bar */}
          <div className="flex gap-1 p-1 bg-slate-900/60 border border-slate-700/40 rounded-xl w-fit">
            {(["rank", "compare", "evidence"] as const).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium capitalize transition-all ${
                  tab === t ? "bg-blue-600/20 text-blue-300 border border-blue-500/30" : "text-slate-500 hover:text-slate-300"
                }`}>
                {t === "rank" ? "🏆 Ranking" : t === "compare" ? "📊 Compare" : "🧠 Evidence"}
              </button>
            ))}
            <span className="ml-4 self-center text-xs text-slate-600 font-mono">{arena.latency_ms}ms</span>
          </div>

          {/* Rankings */}
          {tab === "rank" && (
            <div className="space-y-3">
              {arena.ranking.map((r, i) => {
                const pColor = PRIORITY_COLOR[r.priority] ?? "#64748b";
                return (
                  <div key={r.incident_id}
                    className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4 flex items-start gap-4 fade-in-up"
                    style={{ animationDelay: `${i * 0.1}s` }}>
                    {/* Rank */}
                    <div className="text-3xl font-black w-10 text-center shrink-0"
                      style={{ color: i === 0 ? "#ef4444" : i === 1 ? "#f97316" : "#64748b" }}>
                      {r.rank}
                    </div>
                    {/* Info */}
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="font-mono text-xs text-slate-600">{r.incident_id}</span>
                        <span className="font-semibold text-white capitalize">{r.incident_type}</span>
                        <span className="text-xs font-bold font-mono px-2 py-0.5 rounded border"
                          style={{ color: pColor, borderColor: pColor + "40", background: pColor + "15" }}>
                          {r.priority}
                        </span>
                        <span className="text-xs">{TRIAGE_ICON[r.triage_action]} {r.triage_action.toUpperCase()}</span>
                      </div>
                      <p className="text-xs text-slate-400 mb-1">📍 {r.location}</p>
                      <p className="text-xs text-slate-300">{r.reason}</p>
                      <div className="flex items-center gap-3 mt-2">
                        <div className="flex items-center gap-1.5">
                          <div className="h-1.5 rounded-full bg-slate-800 w-20 overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${r.preliminary_score}%`, background: pColor }} />
                          </div>
                          <span className="text-[10px] font-mono text-slate-500">{r.preliminary_score}/100</span>
                        </div>
                        {r.human_review_required && (
                          <span className="text-[10px] text-amber-400 bg-amber-900/20 border border-amber-600/20 px-2 py-0.5 rounded">
                            ⚠ Human review
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Explanation */}
              <div className="bg-slate-900/40 border border-slate-700/30 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Agent Explanation</p>
                <p className="text-sm text-slate-300 leading-relaxed">{arena.explanation}</p>
              </div>

              {/* Info blocks */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <InfoBlock icon="⚖️" title="Trade-offs" items={arena.trade_offs} />
                <InfoBlock icon="❓" title="Uncertainties" items={arena.unresolved_uncertainties} />
                <InfoBlock icon="🔄" title="What could change it" items={arena.what_could_change_it} />
              </div>

              {/* Change conditions */}
              <div className="bg-amber-900/10 border border-amber-500/20 rounded-xl p-4">
                <p className="font-semibold text-amber-300 mb-1">Change conditions → watch the decision update</p>
                <p className="text-xs text-amber-600 mb-3">
                  The model is called again with the updated state. Nothing is rearranged by hand.
                </p>
                {reassessing && (
                  <div className="flex items-center gap-2 mb-3 text-amber-300 text-sm">
                    <div className="w-4 h-4 border border-amber-400 border-t-transparent rounded-full animate-spin" />
                    Reassessing with updated conditions…
                  </div>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {SCENARIOS.map(s => (
                    <button key={s.label} onClick={() => runReassess(s)} disabled={reassessing}
                      className="text-left bg-slate-800/60 hover:bg-slate-800 border border-amber-500/20 hover:border-amber-500/40 rounded-xl p-3 transition-all disabled:opacity-50">
                      <p className="font-semibold text-amber-300 text-sm mb-1">{s.icon} {s.label}</p>
                      <p className="text-xs text-slate-500 line-clamp-2">{s.note}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Before / after */}
              {reassess && (
                <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
                  <p className="font-semibold text-white mb-3">Before → After reassessment</p>
                  <div className="grid grid-cols-2 gap-4">
                    {[reassess.before, reassess.after].map((a, si) => (
                      <div key={si} className={`rounded-xl border p-3 ${si === 1 ? "border-blue-500/30 bg-blue-500/5" : "border-slate-700/40"}`}>
                        <p className={`text-xs font-bold uppercase mb-2 ${si === 1 ? "text-blue-400" : "text-slate-500"}`}>
                          {si === 0 ? "Before" : "After"}
                        </p>
                        {a.ranking.map(r => (
                          <div key={r.incident_id} className="flex items-center gap-2 mb-1.5">
                            <span className="text-slate-600 text-sm font-bold w-4">{r.rank}</span>
                            <span className="font-mono text-xs text-slate-500">{r.incident_id}</span>
                            <span className="text-xs font-semibold font-mono"
                              style={{ color: PRIORITY_COLOR[r.priority] ?? "#64748b" }}>
                              {r.priority}
                            </span>
                            <span className="text-xs">{TRIAGE_ICON[r.triage_action]}</span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Compare chart */}
          {tab === "compare" && (
            <div className="space-y-4">
              <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Risk Score Comparison</p>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={arena.ranking} barSize={40}>
                    <XAxis dataKey="incident_id" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#475569", fontSize: 10 }} domain={[0, 100]} axisLine={false} tickLine={false} />
                    <Tooltip
                      cursor={{ fill: "rgba(255,255,255,0.02)" }}
                      contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8, fontSize: 11 }}
                    />
                    <Bar dataKey="preliminary_score" radius={[6, 6, 0, 0]}>
                      {arena.ranking.map((r, i) => (
                        <Cell key={i} fill={PRIORITY_COLOR[r.priority] ?? "#64748b"} fillOpacity={0.8} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Multi-factor Comparison</p>
                <ResponsiveContainer width="100%" height={220}>
                  <RadarChart data={arena.ranking.map(r => ({
                    id: r.incident_id,
                    score: r.preliminary_score,
                    priority: r.priority_rank * 25,
                    review: r.human_review_required ? 80 : 20,
                  }))}>
                    <PolarGrid stroke="#1e293b" />
                    <PolarAngleAxis dataKey="id" tick={{ fill: "#64748b", fontSize: 10 }} />
                    <Radar dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={2} />
                    <Radar dataKey="priority" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.10} strokeWidth={1.5} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Decider evidence */}
          {tab === "evidence" && (
            <div className="space-y-3">
              {arena.decisions.map(d => (
                <div key={d.decision_id} className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">
                    {d.decision.incident_id} — {d.decision.triage_action.toUpperCase()}
                    {!d.decision.live_decider && (
                      <span className="ml-2 text-amber-500 normal-case text-[10px]">(simulated)</span>
                    )}
                  </p>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <p className="text-slate-600 mb-1">Priority</p>
                      <p className="font-semibold text-white" style={{ color: PRIORITY_COLOR[d.decision.priority] }}>
                        {d.decision.priority}
                      </p>
                    </div>
                    <div>
                      <p className="text-slate-600 mb-1">Confidence</p>
                      <p className="font-semibold text-white font-mono">{(d.decision.confidence * 100).toFixed(0)}%</p>
                    </div>
                    <div>
                      <p className="text-slate-600 mb-1">Risk score</p>
                      <p className="font-semibold text-white font-mono">{d.decision.preliminary_score}/100</p>
                    </div>
                    <div>
                      <p className="text-slate-600 mb-1">Human review</p>
                      <p className={d.decision.human_review_required ? "text-amber-400" : "text-green-400"}>
                        {d.decision.human_review_required ? "Required" : "Not required"}
                      </p>
                    </div>
                  </div>
                  {d.decision.decider_evidence && (
                    <div className="mt-3 space-y-2">
                      <p className="text-[10px] text-slate-600 uppercase tracking-wide">Priority probabilities</p>
                      {Object.entries(d.decision.decider_evidence.priority_probabilities).map(([k, v]) => (
                        <div key={k} className="flex items-center gap-2 text-xs">
                          <span className="w-16 text-slate-500 capitalize shrink-0">{k}</span>
                          <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${v * 100}%`, background: PRIORITY_COLOR[k.toUpperCase()] ?? "#64748b" }} />
                          </div>
                          <span className="font-mono text-slate-400 w-10 text-right">{(v * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="text-xs text-slate-500 mt-2 line-clamp-2">{d.decision.reason_summary}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!arena && !running && (
        <div className="flex flex-col items-center justify-center py-20 text-slate-600 gap-3">
          <span className="text-5xl">⚔️</span>
          <p className="text-base text-slate-500">Select 2+ incidents and click Run Arena</p>
          <p className="text-sm">The agent evaluates each, ranks them, and explains why.</p>
        </div>
      )}
    </div>
  );
}

function InfoBlock({ icon, title, items }: { icon: string; title: string; items: string[] }) {
  return (
    <div className="bg-slate-900/40 border border-slate-700/30 rounded-xl p-3">
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide mb-2">{icon} {title}</p>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-xs text-slate-400 flex gap-1.5">
            <span className="text-slate-700 shrink-0">·</span>{item}
          </li>
        ))}
      </ul>
    </div>
  );
}
