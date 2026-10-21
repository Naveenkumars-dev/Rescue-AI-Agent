import type { Priority, TriageAction, DecisionStatus } from "../types";

const PRIORITY_STYLES: Record<Priority, string> = {
  CRITICAL: "bg-red-100 text-red-800 border border-red-200",
  HIGH: "bg-orange-100 text-orange-800 border border-orange-200",
  MEDIUM: "bg-yellow-100 text-yellow-800 border border-yellow-200",
  LOW: "bg-green-100 text-green-800 border border-green-200",
  NEEDS_REVIEW: "bg-gray-100 text-gray-700 border border-gray-200",
};

const TRIAGE_STYLES: Record<TriageAction, string> = {
  block: "bg-red-100 text-red-800 border border-red-300",
  review: "bg-yellow-100 text-yellow-800 border border-yellow-200",
  allow: "bg-green-100 text-green-800 border border-green-200",
};

const STATUS_STYLES: Record<DecisionStatus, string> = {
  PROPOSED: "bg-blue-100 text-blue-800 border border-blue-200",
  APPROVED: "bg-green-100 text-green-800 border border-green-200",
  REJECTED: "bg-red-100 text-red-800 border border-red-200",
  NEEDS_MORE_INFORMATION: "bg-purple-100 text-purple-800 border border-purple-200",
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${PRIORITY_STYLES[priority]}`}>
      {priority}
    </span>
  );
}

export function TriageBadge({ action }: { action: TriageAction }) {
  const label = action === "block" ? "🔴 ESCALATE" : action === "review" ? "🟡 REVIEW" : "🟢 ALLOW";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${TRIAGE_STYLES[action]}`}>
      {label}
    </span>
  );
}

export function StatusBadge({ status }: { status: DecisionStatus }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${STATUS_STYLES[status]}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function ModeBadge({ mode, live }: { mode: string; live: boolean }) {
  if (live) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        LIVE
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
      DEMO
    </span>
  );
}
