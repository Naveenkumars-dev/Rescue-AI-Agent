import { useEffect, useState, useCallback } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  getIncidents, createIncident, evaluateDecision,
  approveDecision, rejectDecision, reassessIncident,
} from "../services/api";
import type { IncidentOut, DecisionResponse, IncidentCreate } from "../types";
import IncidentCard from "../components/IncidentCard";
import DecisionPanel from "../components/DecisionPanel";

const EMPTY_FORM: IncidentCreate = {
  type: "", location: "", report: "",
  severity: 3, time_sensitivity: 3, affected_people_num: 0, hazard_level: 1, hazards: "",
};

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<IncidentOut[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<DecisionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<IncidentCreate>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [reassessing, setReassessing] = useState(false);
  const [changeNote, setChangeNote] = useState("");

  const refresh = useCallback(() => {
    setLoading(true);
    getIncidents().then(setIncidents).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const evaluate = async (id: string) => {
    setEvaluating(id);
    setSelected(id);
    setResult(null);
    setError("");
    try {
      const r = await evaluateDecision(id);
      setResult(r);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setEvaluating(null);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createIncident(form);
      setForm(EMPTY_FORM);
      setShowForm(false);
      refresh();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const approve = async (id: string, note: string) => {
    try { await approveDecision(id, note); refresh(); setResult(prev => prev ? { ...prev, decision: { ...prev.decision, decision_status: "APPROVED" } } : null); }
    catch (e: unknown) { setError((e as Error).message); }
  };

  const reject = async (id: string, note: string) => {
    try { await rejectDecision(id, note); refresh(); setResult(prev => prev ? { ...prev, decision: { ...prev.decision, decision_status: "REJECTED" } } : null); }
    catch (e: unknown) { setError((e as Error).message); }
  };

  const handleReassess = async () => {
    if (!selected) return;
    setReassessing(true);
    setError("");
    try {
      const res = await reassessIncident(selected, {
        severity: 5, hazard_level: 5, affected_people_num: 8,
        affected_people: "8 people confirmed affected",
      }, changeNote || "Conditions worsened");
      setResult(res.after);
      refresh();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setReassessing(false);
    }
  };

  return (
    <div className="flex gap-6 h-full">
      {/* Left: incident list */}
      <div className="w-80 shrink-0 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-900">Incidents</h1>
          <button
            onClick={() => setShowForm(!showForm)}
            className="text-sm bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg font-medium transition-colors"
          >
            + New
          </button>
        </div>

        {/* New incident form */}
        {showForm && (
          <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-xl p-4 space-y-3 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-700">Report new incident</h3>
            <Field label="Type" required>
              <input className={INPUT} value={form.type} required placeholder="flood, fire, gas leak…"
                onChange={e => setForm(f => ({ ...f, type: e.target.value }))} />
            </Field>
            <Field label="Location" required>
              <input className={INPUT} value={form.location} required placeholder="Street, district…"
                onChange={e => setForm(f => ({ ...f, location: e.target.value }))} />
            </Field>
            <Field label="Report">
              <textarea className={INPUT} value={form.report} rows={3} placeholder="Free-text description…"
                onChange={e => setForm(f => ({ ...f, report: e.target.value }))} />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              {(["severity", "time_sensitivity", "hazard_level"] as const).map(k => (
                <Field key={k} label={k.replace(/_/g, " ")}>
                  <input type="number" min={1} max={5} className={INPUT} value={form[k]}
                    onChange={e => setForm(f => ({ ...f, [k]: +e.target.value }))} />
                </Field>
              ))}
              <Field label="People (est.)">
                <input type="number" min={0} className={INPUT} value={form.affected_people_num}
                  onChange={e => setForm(f => ({ ...f, affected_people_num: +e.target.value }))} />
              </Field>
            </div>
            <Field label="Hazards">
              <input className={INPUT} value={form.hazards} placeholder="smoke, flooding…"
                onChange={e => setForm(f => ({ ...f, hazards: e.target.value }))} />
            </Field>
            <div className="flex gap-2">
              <button type="submit" disabled={submitting}
                className="flex-1 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg py-2 transition-colors disabled:opacity-50">
                {submitting ? "Submitting…" : "Submit"}
              </button>
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 border border-slate-200 text-slate-600 text-sm rounded-lg hover:bg-slate-50">
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Incident list */}
        {loading ? <Spinner /> : (
          <div className="space-y-3 overflow-y-auto flex-1 pr-1">
            {incidents.filter(i => i.status === "active").map(inc => (
              <IncidentCard
                key={inc.id}
                incident={inc}
                selected={selected === inc.id}
                onClick={() => { setSelected(inc.id); setResult(null); }}
                onEvaluate={() => evaluate(inc.id)}
                loading={evaluating === inc.id}
              />
            ))}
          </div>
        )}
      </div>

      {/* Right: decision panel */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-red-700 text-sm flex justify-between">
            {error}
            <button onClick={() => setError("")} className="text-red-400 hover:text-red-600">✕</button>
          </div>
        )}

        {evaluating && (
          <div className="flex items-center gap-3 bg-blue-50 border border-blue-100 rounded-xl p-5 mb-4">
            <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin shrink-0" />
            <div>
              <p className="text-sm font-medium text-blue-900">Agent evaluating {evaluating}…</p>
              <p className="text-xs text-blue-600 mt-0.5">Running tools, building triage state, invoking Strands Decider 2B</p>
            </div>
          </div>
        )}

        {result && !evaluating && (
          <div className="space-y-4">
            <DecisionPanel result={result} onApprove={approve} onReject={reject} />

            {/* Change conditions */}
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-amber-900 mb-2">🔄 Change conditions & reassess</h3>
              <p className="text-xs text-amber-700 mb-3">
                Simulate worsening conditions (severity→5, hazard→5, 8 people confirmed). The agent will re-run all tools and produce a new decision.
              </p>
              <input
                className="w-full border border-amber-200 bg-white rounded-lg px-3 py-2 text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
                placeholder="Note (optional): e.g. confirmed trapped resident"
                value={changeNote}
                onChange={e => setChangeNote(e.target.value)}
              />
              <button
                onClick={handleReassess}
                disabled={reassessing}
                className="w-full bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-semibold rounded-lg py-2 transition-colors"
              >
                {reassessing ? "Reassessing…" : "Simulate worsening → reassess"}
              </button>
            </div>
          </div>
        )}

        {!result && !evaluating && selected && (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-3">
            <span className="text-4xl">🤖</span>
            <p className="text-sm">Click <strong>Evaluate →</strong> to run the agent on this incident.</p>
          </div>
        )}

        {!selected && (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-3">
            <span className="text-4xl">🚨</span>
            <p className="text-sm">Select an incident to evaluate it.</p>
          </div>
        )}
      </div>
    </div>
  );
}

const INPUT = "w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400";
function Field({ label, children, required }: { label: string; children: ReactNode; required?: boolean }) {
  return (
    <div>
      <label className="text-xs text-slate-500 font-medium mb-1 block capitalize">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}
function Spinner() {
  return <div className="flex justify-center py-8"><div className="w-6 h-6 border-4 border-brand-500 border-t-transparent rounded-full animate-spin" /></div>;
}
