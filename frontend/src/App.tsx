import { useState, useEffect } from "react";
import AgentChat from "./pages/AgentChat";
import MissionControl from "./pages/MissionControl";
import ArenaPage from "./pages/ArenaPage";
import DecisionsPage from "./pages/DecisionsPage";

type Page = "chat" | "mission" | "arena" | "history";

const NAV = [
  { id: "chat" as Page,    icon: "🤖", label: "Agent" },
  { id: "mission" as Page, icon: "🛰", label: "Mission Control" },
  { id: "arena" as Page,   icon: "⚔️", label: "Decision Arena" },
  { id: "history" as Page, icon: "📋", label: "History" },
];

export default function App() {
  const [page, setPage] = useState<Page>("chat");
  const [agentActive, setAgentActive] = useState(false);

  // pulse the nav icon when agent is working
  useEffect(() => {
    const handler = (e: Event) => setAgentActive((e as CustomEvent).detail);
    window.addEventListener("agent-active", handler);
    return () => window.removeEventListener("agent-active", handler);
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0e1a] grid-bg flex flex-col">

      {/* Top bar */}
      <header className="border-b border-slate-800 bg-[#0d1120]/80 backdrop-blur-sm px-5 py-3 flex items-center gap-4 sticky top-0 z-40">
        {/* Logo */}
        <div className="flex items-center gap-3 mr-2">
          <div className="relative">
            <div className={`w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-lg shadow-lg ${agentActive ? "glow-pulse" : ""}`}>
              🌊
            </div>
            {agentActive && (
              <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-green-400 rounded-full border border-[#0d1120]">
                <span className="absolute inset-0 rounded-full bg-green-400 ping-slow" />
              </span>
            )}
          </div>
          <div>
            <p className="text-sm font-bold text-white leading-none">RescueFlow AI</p>
            <p className="text-[10px] text-slate-500 leading-none mt-0.5 font-mono">emergency triage agent</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex gap-1">
          {NAV.map(n => (
            <button key={n.id} onClick={() => setPage(n.id)}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${
                page === n.id
                  ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/50"
              }`}>
              <span className="text-base leading-none">{n.icon}</span>
              <span className="hidden sm:inline">{n.label}</span>
            </button>
          ))}
        </nav>

        {/* Status pill */}
        <div className="ml-auto flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/60 border border-slate-700/50">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <span className="text-xs text-slate-400 font-mono">demo mode</span>
          </div>
          <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer"
            className="text-xs text-slate-600 hover:text-slate-400 transition-colors px-2 py-1">
            API ↗
          </a>
        </div>
      </header>

      {/* Page */}
      <main className="flex-1 overflow-hidden">
        {page === "chat"    && <AgentChat    onActivity={a => window.dispatchEvent(new CustomEvent("agent-active", { detail: a }))} />}
        {page === "mission" && <MissionControl />}
        {page === "arena"   && <ArenaPage />}
        {page === "history" && <DecisionsPage />}
      </main>
    </div>
  );
}
