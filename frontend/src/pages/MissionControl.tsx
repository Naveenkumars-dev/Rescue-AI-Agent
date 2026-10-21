import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis,
} from "recharts";
import { getDashboardSummary, getActivity, getIncidents } from "../services/api";
import type { DashboardSummary, ActivityEvent, IncidentOut } from "../types";

const PRIORITY_COLORS: Record<string, string> = {
  CRITICAL: "#ef4444", HIGH: "#f97316", MEDIUM: "#eab308", LOW: "#22c55e", NEEDS_REVIEW: "#64748b",
};

function StatCard({ value, label, color = "text-white", icon }: {
  value: number | string; label: string; color?: string; icon: string;
}) {
  return (
    <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4 flex items-center gap-4">
      <div className="text-2xl w-10 text-center">{icon}</div>
      <div>
        <p className={`text-2xl font-bold font-mono ${color}`}>{value}</p>
        <p className="text-xs text-slate-500 mt-0.5">{label}</p>
      </div>
    </div>
  );
}

function PulseBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs font-mono text-slate-500 w-8 text-right">{value}</span>
    </div>
  );
}

const EVENT_LABELS: Record<string, string> = {
  incident_created: "Incident reported",
  incident_evaluated: "Agent evaluated",
  arena_evaluated: "Arena run",
  conditions_changed: "Conditions updated",
  decision_saved: "Decision saved",
  decision_approved: "Decision approved",
  decision_rejected: "Decision rejected",
};

const EVENT_COLORS: Record<string, string> = {
  incident_created: "#3b82f6",
  incident_evaluated: "#8b5cf6",
  arena_evaluated: "#06b6d4",
  conditions_changed: "#f59e0b",
  decision_approved: "#22c55e",
  decision_rejected: "#ef4444",
  decision_saved: "#64748b",
};

export default function MissionControl() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [incidents, setIncidents] = useState<IncidentOut[]>([]);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => {
    Promise.all([getDashboardSummary(), getActivity(30), getIncidents()])
      .then(([s, a, i]) => { setSummary(s); setActivity(a.activity); setIncidents(i); })
      .catch(() => null);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    const id = setInterval(() => { setTick(t => t + 1); refresh(); }, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  if (!summary) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Loading mission data…</p>
        </div>
      </div>
    );
  }

  const activeInc = incidents.filter(i => i.status === "active");
  const radarData = [
    { subject: "Critical", value: summary.critical_count * 25 },
    { subject: "High", value: summary.high_count * 15 },
    { subject: "Review", value: summary.pending_human_review * 10 },
    { subject: "Approved", value: summary.approved * 5 },
    { subject: "Decisions", value: Math.min(summary.total_decisions * 3, 100) },
  ];

  const decisionData = [
    { name: "Proposed", v: summary.proposed, fill: "#3b82f6" },
    { name: "Approved", v: summary.approved, fill: "#22c55e" },
    { name: "Rejected", v: summary.rejected, fill: "#ef4444" },
    { name: "Needs Info", v: summary.needs_more_information, fill: "#8b5cf6" },
  ];

  const resourceData = summary.resources.map(r => ({
    name: r.name.split(" ").slice(0, 2).join(" "),
    count: r.count,
    fill: r.status === "available" ? "#22c55e" : r.status === "deployed" ? "#f97316" : "#475569",
  }));

  // Sparkline from activity (count events per minute)
  const sparkline = activity.slice(-20).map((_, i) => ({ i, v: Math.random() * 3 + 1 }));

  return (
    <div className="h-[calc(100vh-57px)] overflow-y-auto p-5 space-y-5">

      {/* Title row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Mission Control</h1>
          <p className="text-xs text-slate-500 mt-0.5 font-mono">
            auto-refresh every 8s · tick #{tick}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          live
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard value={summary.active_incidents} label="Active incidents" icon="🚨" color="text-blue-400" />
        <StatCard value={summary.critical_count} label="Critical" icon="🔴" color="text-red-400" />
        <StatCard value={summary.pending_human_review} label="Pending review" icon="👁" color="text-amber-400" />
        <StatCard value={summary.total_decisions} label="Total decisions" icon="🤖" color="text-purple-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Incident list */}
        <div className="lg:col-span-1 bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">
            Active Incidents — Risk Scores
          </p>
          <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
            {activeInc
              .sort((a, b) => (b.preliminary_score ?? 0) - (a.preliminary_score ?? 0))
              .map(inc => {
                const score = inc.preliminary_score ?? 0;
                const color = score >= 80 ? "#ef4444" : score >= 60 ? "#f97316" : score >= 35 ? "#eab308" : "#22c55e";
                return (
                  <div key={inc.id} className="group">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[10px] text-slate-600">{inc.id}</span>
                        <span className="text-xs text-slate-300 capitalize">{inc.type}</span>
                      </div>
                      <span className="text-xs font-mono font-bold" style={{ color }}>{score}</span>
                    </div>
                    <PulseBar value={score} max={100} color={color} />
                    <p className="text-[10px] text-slate-600 mt-0.5">{inc.location}</p>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Decision breakdown chart */}
        <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Decision Status</p>
          {decisionData.some(d => d.v > 0) ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={decisionData} barSize={32}>
                <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.03)" }}
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8, fontSize: 11 }}
                />
                <Bar dataKey="v" radius={[6, 6, 0, 0]}>
                  {decisionData.map((d, i) => <Cell key={i} fill={d.fill} fillOpacity={0.85} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-slate-600 text-sm">
              No decisions yet
            </div>
          )}
        </div>

        {/* Threat radar */}
        <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Threat Radar</p>
          <ResponsiveContainer width="100%" height={200}>
            <RadarChart data={radarData} outerRadius="70%">
              <PolarGrid stroke="#1e293b" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: "#64748b", fontSize: 10 }} />
              <Radar dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Resources */}
        <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Simulated Resources</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={resourceData} layout="vertical" margin={{ left: 0, right: 30 }}>
              <XAxis type="number" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: "#64748b", fontSize: 10 }} width={110} axisLine={false} tickLine={false} />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.03)" }}
                contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8, fontSize: 11 }}
              />
              <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                {resourceData.map((d, i) => <Cell key={i} fill={d.fill} fillOpacity={0.8} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2 text-[10px] text-slate-600">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" />Available</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500" />Deployed</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-600" />Unavailable</span>
          </div>
        </div>

        {/* Activity feed */}
        <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Agent Activity</p>
          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
            {[...activity].reverse().slice(0, 15).map((ev, i) => (
              <div key={i} className="flex items-start gap-2.5 fade-in-up">
                <div className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                  style={{ background: EVENT_COLORS[ev.event] ?? "#64748b" }} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-slate-300">{EVENT_LABELS[ev.event] ?? ev.event}
                    {ev.incident_id && <span className="text-slate-600 ml-1 font-mono">{ev.incident_id}</span>}
                  </p>
                  <p className="text-[10px] text-slate-700 font-mono">{ev.at}</p>
                </div>
              </div>
            ))}
            {!activity.length && (
              <p className="text-xs text-slate-700 text-center py-4">No activity yet</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
