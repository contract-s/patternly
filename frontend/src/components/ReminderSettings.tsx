import { type FormEvent, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { Reminders } from '../api/types'
import { hourLabel } from '../hours'

const HOURS = Array.from({ length: 24 }, (_, h) => h)

/** Whether to get the daily reminder email, and the local hour it goes out. */
export default function ReminderSettings({ initial, timezone }: { initial: Reminders; timezone: string }) {
  const [enabled, setEnabled] = useState(initial.enabled)
  const [hour, setHour] = useState(initial.hour)
  const [saved, setSaved] = useState(initial)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [error, setError] = useState<string | null>(null)
  const changed = enabled !== saved.enabled || hour !== saved.hour

  async function save(e: FormEvent) {
    e.preventDefault()
    setStatus('saving')
    setError(null)
    try {
      setSaved(await api.setReminders({ enabled, hour }))
      setStatus('saved')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save')
      setStatus('idle')
    }
  }

  return (
    <aside className="card reminders" aria-label="Reminder emails">
      <h3>Reminder emails</h3>
      <form onSubmit={save}>
        <label className="check">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => {
              setEnabled(e.target.checked)
              setStatus('idle')
            }}
          />
          Email me if today's lesson isn't done
        </label>
        <label>
          Send it at{' '}
          <select
            value={hour}
            disabled={!enabled}
            onChange={(e) => {
              setHour(Number(e.target.value))
              setStatus('idle')
            }}
          >
            {HOURS.map((h) => (
              <option key={h} value={h}>
                {hourLabel(h)}
              </option>
            ))}
          </select>{' '}
          <span className="muted">({timezone})</span>
        </label>
        <div className="row">
          <button type="submit" disabled={!changed || status === 'saving'}>
            {status === 'saving' ? 'Saving…' : 'Save'}
          </button>
          {status === 'saved' && !changed && <span className="muted">Saved</span>}
          {error && <span className="error">{error}</span>}
        </div>
      </form>
    </aside>
  )
}
