import { useState } from 'react'
import { createIncident } from '../services/api'

interface Props {
  onCreated: () => void
}

export function IncidentForm({ onCreated }: Props) {
  const [report, setReport] = useState('')
  const [type, setType] = useState('')
  const [location, setLocation] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!report.trim()) return
    setLoading(true)
    setError('')
    try {
      await createIncident({
        report: report.trim(),
        type: type.trim() || 'unknown',
        location: location.trim() || 'unknown',
        status: 'active',
        report_time: new Date().toISOString().slice(0, 16).replace('T', ' '),
        affected_people: 'unknown',
        affected_people_num: 0,
        hazards: 'unknown',
        time_sensitivity: 3,
        severity: 3,
        hazard_level: 3,
      })
      setReport('')
      setType('')
      setLocation('')
      onCreated()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create incident')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <label className="text-xs text-mute block mb-1">Incident Type</label>
        <input
          className="input-field text-sm"
          placeholder="e.g. flood, fire, road obstruction"
          value={type}
          onChange={e => setType(e.target.value)}
        />
      </div>
      <div>
        <label className="text-xs text-mute block mb-1">Location</label>
        <input
          className="input-field text-sm"
          placeholder="e.g. Riverside area"
          value={location}
          onChange={e => setLocation(e.target.value)}
        />
      </div>
      <div>
        <label className="text-xs text-mute block mb-1">Incident Report *</label>
        <textarea
          className="input-field text-sm resize-none"
          rows={3}
          placeholder="Describe the incident in plain language..."
          value={report}
          onChange={e => setReport(e.target.value)}
          required
        />
      </div>
      {error && <p className="text-red-400 text-xs">{error}</p>}
      <button type="submit" className="btn-primary w-full" disabled={loading || !report.trim()}>
        {loading ? 'Submitting…' : 'Submit Incident'}
      </button>
    </form>
  )
}
