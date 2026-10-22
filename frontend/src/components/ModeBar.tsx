import { useEffect, useState } from "react";
import { getInfo } from "../services/api";
import type { ModeInfo } from "../types";

export default function ModeBar() {
  const [info, setInfo] = useState<ModeInfo | null>(null);

  useEffect(() => {
    getInfo().then(setInfo).catch(() => null);
  }, []);

  if (!info) return null;

  const isLive = info.mode === "live";

  return (
    <div className={`w-full text-xs px-4 py-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 ${
      isLive ? "bg-emerald-950 text-emerald-300" : "bg-amber-950 text-amber-300"
    }`}>
      <span className="flex items-center gap-1 font-semibold">
        <span className={`w-2 h-2 rounded-full ${isLive ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
        {isLive ? "LIVE MODE — Strands Decider 2B + Strands Agent" : "⚠ DEMO MODE — simulated decisions, no live model"}
      </span>
      {!isLive && (
        <span className="opacity-80">
          {info.reason}
        </span>
      )}
      {isLive && (
        <>
          <span className="opacity-70">decider: {info.decider_mode}</span>
          <span className="opacity-70">llm: {info.llm_provider} ({info.llm_model_id})</span>
        </>
      )}
      <span className="ml-auto opacity-50 italic">{info.kit_credit}</span>
    </div>
  );
}
