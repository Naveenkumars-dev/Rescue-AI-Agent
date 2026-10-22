import { useState, useRef, useEffect, useCallback } from "react";
import { getIncidents, resetDemo } from "../services/api";
import type { IncidentOut, DecisionResponse, ToolCall } from "../types";

interface AgentStep {
  step: number;
  icon: string;
  tool: string;
  message: string;
  done: boolean;
}

interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  incident?: IncidentOut;
  result?: DecisionResponse;
  steps?: AgentStep[];
  isStreaming?: boolean;
  error?: string;
  ts: number;
}

const PRIORITY_COLORS: Record<string, string> = {
  CRITICAL: "text-red-400 border-red-500/40 bg-red-500/10",
  HIGH:     "text-orange-400 border-orange-500/40 bg-orange-500/10",
  MEDIUM:   "text-yellow-400 border-yellow-500/40 bg-yellow-500/10",
  LOW:      "text-green-400 border-green-500/40 bg-green-500/10",
  NEEDS_REVIEW: "text-slate-400 border-slate-500/40 bg-slate-500/10",
};

const TRIAGE_CONFIG: Record<string, { color: string; label: string; icon: string }> = {
  block:  { color: "text-red-400",    label: "ESCALATE",        icon: "🔴" },
  review: { color: "text-amber-400",  label: "HUMAN REVIEW",    icon: "🟡" },
  allow:  { color: "text-emerald-400",label: "RECOMMEND PLAN",  icon: "🟢" },
};

const QUICK_INCIDENTS = [
  { id: "INC-001", label: "🌊 Flood — Riverside" },
  { id: "INC-002", label: "🚧 Road — Oak Lane" },
  { id: "INC-003", label: "⚡ Power — Market Sq" },
  { id: "INC-004", label: "🔥 Fire — Pine St" },
  { id: "INC-005", label: "💨 Gas Leak" },
];

export default function AgentChat({ onActivity }: { onActivity: (v: boolean) => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "agent",
      content: "RescueFlow AI online. I evaluate emergency incidents, rank competing priorities, and propose response plans.\n\nSelect an incident below or describe a new emergency to begin.",
      ts: Date.now(),
    },
  ]);
  const [incidents, setIncidents] = useState<IncidentOut[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [selectedInc, setSelectedInc] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getIncidents().then(d => setIncidents(d.filter(i => i.status === "active"))).catch(() => null);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addMsg = useCallback((msg: Omit<ChatMessage, "id" | "ts">) => {
    const id = Math.random().toString(36).slice(2);
    setMessages(prev => [...prev, { ...msg, id, ts: Date.now() }]);
    return id;
  }, []);

  const updateMsg = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, ...patch } : m));
  }, []);

  const evaluateIncident = useCallback(async (incidentId: string) => {
    if (running) return;
    setRunning(true);
    onActivity(true);

    const inc = incidents.find(i => i.id === incidentId);

    // User message
    addMsg({ role: "user", content: `Evaluate ${incidentId}${inc ? ` — ${inc.type} at ${inc.location}` : ""}`, incident: inc });

    // Agent thinking message
    const agentId = addMsg({
      role: "agent",
      content: "",
      isStreaming: true,
      steps: [],
    });

    // Stream via SSE
    try {
      const es = new EventSource(`http://127.0.0.1:8000/api/decisions/stream/${incidentId}`);
      const steps: AgentStep[] = [];

      es.onmessage = (e) => {
        const data = JSON.parse(e.data);

        if (data.type === "start") {
          updateMsg(agentId, {
            content: `Initialising agent for ${data.incident_id}…`,
            steps: [],
          });
        }

        if (data.type === "step") {
          const step: AgentStep = {
            step: data.step,
            icon: data.icon,
            tool: data.tool,
            message: data.message,
            done: false,
          };
          // Mark previous as done
          const updated = steps.map(s => ({ ...s, done: true }));
          updated.push(step);
          steps.length = 0;
          steps.push(...updated);
          updateMsg(agentId, { steps: [...steps], content: data.message });
        }

        if (data.type === "complete") {
          es.close();
          const result: DecisionResponse = data.result;
          const allDone = steps.map(s => ({ ...s, done: true }));
          updateMsg(agentId, {
            isStreaming: false,
            content: result.decision.reason_summary,
            steps: allDone,
            result,
          });
          setRunning(false);
          onActivity(false);
          // Refresh incidents
          getIncidents().then(d => setIncidents(d.filter(i => i.status === "active"))).catch(() => null);
        }

        if (data.type === "error") {
          es.close();
          updateMsg(agentId, { isStreaming: false, error: data.message, content: "Agent error." });
          setRunning(false);
          onActivity(false);
        }
      };

      es.onerror = () => {
        es.close();
        updateMsg(agentId, { isStreaming: false, error: "Connection lost.", content: "Connection error." });
        setRunning(false);
        onActivity(false);
      };
    } catch {
      updateMsg(agentId, { isStreaming: false, error: "Failed to connect.", content: "Failed." });
      setRunning(false);
      onActivity(false);
    }
  }, [running, incidents, addMsg, updateMsg, onActivity]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const txt = input.trim();
    if (!txt || running) return;
    setInput("");

    // Check if it looks like an incident ID
    const match = txt.match(/INC-\d+/i);
    if (match) {
      evaluateIncident(match[0].toUpperCase());
      return;
    }

    // General query — just echo agent response
    addMsg({ role: "user", content: txt });
    setTimeout(() => {
      addMsg({
        role: "agent",
        content: `To evaluate an incident, select one from the panel or type its ID (e.g. INC-001). I can triage any of the ${incidents.length} active incidents.`,
      });
    }, 400);
  };

  const handleReset = async () => {
    await resetDemo();
    getIncidents().then(d => setIncidents(d.filter(i => i.status === "active"))).catch(() => null);
    setMessages([{
      id: "welcome-reset",
      role: "system",
      content: "Demo data reset. All incidents restored to seed state.",
      ts: Date.now(),
    }]);
  };

  return (
    <div className="flex h-[calc(100vh-57px)]">

      {/* Left sidebar — incident selector */}
      <aside className="w-64 border-r border-slate-800 bg-[#0d1120]/60 flex flex-col shrink-0">
        <div className="p-4 border-b border-slate-800">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Active Incidents</p>
          <div className="space-y-1.5">
            {incidents.slice(0, 10).map(inc => {
              const score = inc.preliminary_score ?? 0;
              const scoreColor = score >= 80 ? "bg-red-500" : score >= 60 ? "bg-orange-500" : score >= 35 ? "bg-yellow-500" : "bg-green-500";
              return (
                <button
                  key={inc.id}
                  onClick={() => { setSelectedInc(inc.id); evaluateIncident(inc.id); }}
                  disabled={running}
                  className={`w-full text-left px-3 py-2.5 rounded-lg border transition-all disabled:opacity-40 group ${
                    selectedInc === inc.id
                      ? "border-blue-500/50 bg-blue-500/10 text-blue-300"
                      : "border-slate-700/50 hover:border-slate-600 bg-slate-800/30 text-slate-300 hover:bg-slate-800/60"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-slate-500">{inc.id}</span>
                    <span className="text-xs font-mono text-slate-500">{score}</span>
                  </div>
                  <p className="text-xs font-medium capitalize truncate">{inc.type}</p>
                  <div className="flex items-center gap-1.5 mt-1.5">
                    <div className="flex-1 h-1 rounded-full bg-slate-700 overflow-hidden">
                      <div className={`h-full ${scoreColor} rounded-full transition-all`} style={{ width: `${score}%` }} />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="p-4 mt-auto border-t border-slate-800">
          <button onClick={handleReset}
            className="w-full text-xs text-slate-500 hover:text-slate-300 py-2 rounded-lg border border-slate-700/50 hover:border-slate-600 transition-colors">
            ↺ Reset demo data
          </button>
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {messages.map(msg => (
            <MessageBubble key={msg.id} msg={msg} onEval={evaluateIncident} running={running} />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-slate-800 bg-[#0d1120]/80 px-6 py-4">
          <form onSubmit={handleSubmit} className="flex gap-3 items-center">
            <div className="flex-1 relative">
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                disabled={running}
                placeholder={running ? "Agent is processing…" : "Type INC-001 or describe an incident…"}
                className="w-full bg-slate-800/60 border border-slate-700/60 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500/60 focus:bg-slate-800 transition-all disabled:opacity-50 font-mono"
              />
              {running && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex gap-1">
                  {[0, 1, 2].map(i => (
                    <div key={i} className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              )}
            </div>
            <button type="submit" disabled={running || !input.trim()}
              className="px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm font-semibold transition-all shrink-0">
              Send
            </button>
          </form>

          {/* Quick picks */}
          <div className="flex gap-2 mt-3 flex-wrap">
            {QUICK_INCIDENTS.map(q => (
              <button key={q.id} onClick={() => evaluateIncident(q.id)} disabled={running}
                className="text-xs px-3 py-1.5 rounded-full border border-slate-700/60 text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-all disabled:opacity-40">
                {q.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Message bubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg, onEval, running }: {
  msg: ChatMessage;
  onEval: (id: string) => void;
  running: boolean;
}) {
  if (msg.role === "system") {
    return (
      <div className="flex justify-center">
        <span className="text-xs text-slate-600 bg-slate-800/40 border border-slate-700/30 px-3 py-1 rounded-full">
          {msg.content}
        </span>
      </div>
    );
  }

  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%]">
          {msg.incident && (
            <div className="mb-2 px-3 py-2 rounded-xl bg-slate-800/40 border border-slate-700/30 text-xs text-slate-400">
              <span className="capitalize">{msg.incident.type}</span> · {msg.incident.location} · score {msg.incident.preliminary_score}
            </div>
          )}
          <div className="px-4 py-3 rounded-2xl rounded-tr-sm bg-blue-600/20 border border-blue-500/30 text-sm text-blue-100">
            {msg.content}
          </div>
        </div>
      </div>
    );
  }

  // Agent message
  return (
    <div className="flex gap-3 items-start max-w-[90%]">
      {/* Avatar */}
      <div className={`shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-sm shadow-lg mt-0.5 ${msg.isStreaming ? "glow-pulse" : ""}`}>
        🤖
      </div>

      <div className="flex-1 space-y-3">
        {/* Thinking/streaming steps */}
        {msg.steps && msg.steps.length > 0 && (
          <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-3 space-y-1.5">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-2">
              {msg.isStreaming ? "Running agent…" : "Execution trace"}
            </p>
            {msg.steps.map((s, i) => (
              <div key={i} className={`flex items-center gap-2.5 text-xs transition-all ${s.done ? "opacity-60" : "fade-in-up"}`}>
                <span className="w-5 text-center shrink-0">{s.done ? "✓" : s.icon}</span>
                <span className={`font-mono shrink-0 ${s.done ? "text-slate-600" : "text-blue-400"}`}>
                  {s.tool}
                </span>
                <span className={s.done ? "text-slate-600" : "text-slate-300"}>{s.message}</span>
                {!s.done && msg.isStreaming && (
                  <span className="ml-auto flex gap-0.5">
                    {[0,1,2].map(j => (
                      <span key={j} className="w-1 h-1 bg-blue-400 rounded-full animate-bounce"
                        style={{ animationDelay: `${j*0.1}s` }} />
                    ))}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Main response text */}
        {(msg.content || msg.isStreaming) && !msg.error && (
          <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-slate-800/50 border border-slate-700/40 text-sm text-slate-200 leading-relaxed">
            {msg.content}
            {msg.isStreaming && <span className="cursor-blink text-blue-400 ml-0.5">▋</span>}
          </div>
        )}

        {/* Error */}
        {msg.error && (
          <div className="px-4 py-3 rounded-xl bg-red-900/20 border border-red-500/30 text-sm text-red-300">
            ⚠ {msg.error}
          </div>
        )}

        {/* Decision card */}
        {msg.result && <DecisionCard result={msg.result} />}
      </div>
    </div>
  );
}

// ─── Decision card ──────────────────────────────────────────────────────────────

function DecisionCard({ result }: { result: DecisionResponse }) {
  const d = result.decision;
  const triage = TRIAGE_CONFIG[d.triage_action] ?? TRIAGE_CONFIG.review;
  const priStyle = PRIORITY_COLORS[d.priority] ?? PRIORITY_COLORS.NEEDS_REVIEW;
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-slate-600/40 bg-slate-900/80 overflow-hidden">

      {/* Header strip */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-700/40 bg-slate-800/30">
        <div className="flex items-center gap-2">
          <span className="text-lg">{triage.icon}</span>
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold font-mono ${triage.color}`}>{triage.label}</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded border font-mono ${priStyle}`}>
                {d.priority}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-mono mt-0.5">{result.decision_id} · {d.incident_id}</p>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="text-center">
            <p className="text-lg font-bold text-white font-mono">{d.preliminary_score ?? "—"}</p>
            <p className="text-[9px] text-slate-500">risk /100</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-white font-mono">{(d.confidence * 100).toFixed(0)}%</p>
            <p className="text-[9px] text-slate-500">{d.live_decider ? "confidence" : "simulated"}</p>
          </div>
          {!d.live_decider && (
            <span className="text-[9px] bg-amber-900/30 border border-amber-600/30 text-amber-400 px-2 py-0.5 rounded font-mono">
              SIMULATED
            </span>
          )}
        </div>
      </div>

      {/* Reason */}
      <div className="px-4 py-3">
        <p className="text-sm text-slate-300 leading-relaxed">{d.reason_summary}</p>
      </div>

      {/* Recommended action */}
      {d.response_plan && (
        <div className="mx-4 mb-3 px-3 py-2.5 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <p className="text-[10px] font-semibold text-blue-400 uppercase tracking-wide mb-1">Recommended action</p>
          <p className="text-xs text-blue-200">{d.response_plan}</p>
        </div>
      )}

      {/* Missing info */}
      {d.missing_information.length > 0 && (
        <div className="mx-4 mb-3 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <p className="text-[10px] font-semibold text-amber-400 uppercase tracking-wide mb-1">⚠ Missing information</p>
          <p className="text-xs text-amber-200">{d.missing_information.join(" · ")}</p>
        </div>
      )}

      {/* Tool call summary bar */}
      <div className="px-4 pb-3">
        <button onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-2 text-xs text-slate-500 hover:text-slate-300 transition-colors py-1">
          <div className="flex gap-1">
            {result.tool_calls.map((tc, i) => (
              <ToolPip key={i} tool={tc} />
            ))}
          </div>
          <span className="ml-auto">{expanded ? "▲ hide" : "▼ show tools"}</span>
        </button>

        {expanded && (
          <div className="mt-2 space-y-1 border-t border-slate-700/40 pt-2">
            {result.tool_calls.map((tc, i) => (
              <ToolRow key={i} tc={tc} />
            ))}
            <p className="text-[10px] text-slate-600 pt-1">{result.latency_ms} ms · {result.model_id}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function ToolPip({ tool }: { tool: ToolCall }) {
  const ICONS: Record<string, string> = {
    get_incident_details: "🔍", list_active_incidents: "📋",
    get_resource_status: "🚒", calculate_preliminary_risk: "📊",
    identify_information_gaps: "⚠️", compare_incidents: "⚖️",
    propose_response_plan: "📝", save_decision_record: "💾",
  };
  return (
    <span title={tool.name}
      className="w-5 h-5 rounded bg-slate-700/60 border border-slate-600/40 flex items-center justify-center text-[10px]">
      {ICONS[tool.name] ?? "🔧"}
    </span>
  );
}

function ToolRow({ tc }: { tc: ToolCall }) {
  const ICONS: Record<string, string> = {
    get_incident_details: "🔍", list_active_incidents: "📋",
    get_resource_status: "🚒", calculate_preliminary_risk: "📊",
    identify_information_gaps: "⚠️", compare_incidents: "⚖️",
    propose_response_plan: "📝", save_decision_record: "💾",
  };
  const [open, setOpen] = useState(false);
  return (
    <div className="text-xs">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left hover:text-slate-300 text-slate-500 transition-colors py-0.5">
        <span>{ICONS[tc.name] ?? "🔧"}</span>
        <span className="font-mono">{tc.name}</span>
        <span className="ml-auto text-slate-700">{tc.latency_ms}ms</span>
        <span className="text-slate-700">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <pre className="ml-5 mt-1 p-2 bg-slate-800/60 rounded text-[10px] text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-32">
          {JSON.stringify(tc.result, null, 2)}
        </pre>
      )}
    </div>
  );
}
