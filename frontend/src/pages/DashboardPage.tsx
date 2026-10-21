import { useEffect, useState, useCallback } from "react";
import {
  RadialBarChart, RadialBar, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, Cell,
} from "recharts";
import { getDashboardSummary, getActivity, resetDemo } from "../services/api";
import type { DashboardSummary, ActivityEvent } from "../types";
import ActivityTimeline from "../components/ActivityTimeline";

const SUMMARY_CARDS = [
  { key: "active_incidents", label: "Active Incidents", icon: "🚨", color: "text-slate-800" },
  { key: "critical_count", label: "Critical", icon: "🔴", color: "text-red-600" },
  { key: "high_count", label: "High Priority", icon: "🟠", color: "text-orange-600" },
  { key: "pending_human_review", label: "Pending Review", icon: "👁", color: "text-amber-600" },
  { key: "total_decisions", label: "Total Decisions", icon: "📋", color: "text-slate-700" },
  { key: "approved", label: "Approved", icon: "✅", color: "text-green-600" },
];

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    Promise.all([getDashboardSummary(), getActivity(50)])
      .then(([s, a]) => { setSummary(s); setActivity(a.activity); setError(""); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10000);
    return () => clearInterval(id);
  }, [refresh]);

  const handleReset = async () => {
    if (!confirm("Reset all demo data to the seed incidents?")) return;
    setResetting(true);
    try {
      await resetDemo();
      await refresh();
    } finally {
      setResetting(false);
    }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner msg={error} />;
  if (!summary) return null;

  const decisionBreakdown = [
    { name: "Proposed", value: summary.proposed, color: "#3b82f6" },
    { name: "Approved", value: summary.approved, color: "#22c55e" },
    { name: "Rejected", value: summary.rejected, color: "#ef4444" },
    { name: "Needs Info", value: summary.needs_more_information, color: "#8b5cf6" },
  ].filter(d => d.value > 0);

  const resourceData = summary.resources.map(r => ({
    name: r.name.length > 22 ? r.name.slice(0, 20) + "…" : r.name,
    count: r.count,
    fill: r.status === "available" ? "#22c55e" : r.status === "deployed" ? "#f97316" : "#94a3b8",
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-slate-500 text-sm mt-0.5">Live incident overview — simulated data</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleReset}
            disabled={resetting}
            className="text-sm px-4 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors disabled:opacity-50"
          >
            {resetting ? "Resetting…" : "↺ Reset demo data"}
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {SUMMARY_CARDS.map(({ key, label, icon, color }) => (
          <div key={key} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm text-center">
            <div className="text-2xl mb-1">{icon}</div>
            <div className={`text-2xl font-bold ${color}`}>
              {summary[key as keyof DashboardSummary] as number}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Decision breakdown */}
        {decisionBreakdown.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">Decision breakdown</h2>
            <ResponsiveContainer width="100%" height={180}>
              <RadialBarChart innerRadius="30%" outerRadius="90%" data={decisionBreakdown} startAngle={90} endAngle={-270}>
                <RadialBar dataKey="value" label={{ position: "insideStart", fill: "#fff", fontSize: 11 }} />
                <Tooltip formatter={(v: number, n: string) => [v, n]} contentStyle={{ fontSize: 12 }} />
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap gap-2 mt-2 justify-center">
              {decisionBreakdown.map(d => (
                <span key={d.name} className="flex items-center gap-1 text-xs text-slate-600">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: d.color }} />
                  {d.name} ({d.value})
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Resources */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Simulated resources</h2>
          {resourceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={resourceData} layout="vertical" margin={{ left: 0, right: 20 }}>
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={130} />
                <Tooltip contentStyle={{ fontSize: 12 }} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {resourceData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-slate-400 text-sm">No resources loaded.</p>}
          <div className="flex gap-3 mt-2 text-xs text-slate-500">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" />Available</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500" />Deployed</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-400" />Unavailable</span>
          </div>
        </div>

        {/* Activity */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm overflow-y-auto max-h-72">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Agent activity</h2>
          <ActivityTimeline events={activity} />
        </div>
      </div>
    </div>
  );
}

function Spinner() {
  return <div className="flex items-center justify-center py-16"><div className="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin" /></div>;
}
function ErrorBanner({ msg }: { msg: string }) {
  return <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">Error: {msg}</div>;
}
