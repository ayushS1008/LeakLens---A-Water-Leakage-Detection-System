import { useState } from 'react'
import { apiRequest } from './api'
import { numbers, fullDate } from './analysis'

export default function Households({ households, activeId, onSelect, onCreated }) {
  const [name, setName] = useState('')
  const [id, setId] = useState('')
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function create(event) {
    event.preventDefault()
    if (!file) return
    setBusy(true); setError(''); setNotice('')
    const form = new FormData()
    form.append('name', name); form.append('household_id', id); form.append('timezone', timezone); form.append('file', file)
    try {
      const household = await apiRequest('/households', { method: 'POST', body: form })
      onCreated(household)
      setNotice(`${household.name} is ready. Select it to analyse that household’s readings.`)
      setName(''); setId('')
    } catch (failure) { setError(failure.message) } finally { setBusy(false) }
  }

  return <>
    <div className="page-heading"><p className="eyebrow">HOUSEHOLDS</p><h1>Every home has its own rhythm.</h1><p>Give each household a profile and a detector that learns from its own history.</p></div>
    {notice && <div className="action-notice" role="status">{notice}</div>}
    <div className="household-cards">{households.map((home) => <article key={home.household_id} className={`panel household-card ${home.household_id === activeId ? 'active' : ''}`}><div className="household-card-top"><span className="home-symbol" aria-hidden="true">⌂</span><span className="status-badge ticket-saved">{home.built_in ? 'Built-in profile' : 'Personalised model'}</span></div><h2>{home.name}</h2><p>{home.household_id} · {home.timezone}</p><dl><div><dt>Training readings</dt><dd>{numbers.format(home.training_rows)}</dd></div><div><dt>Calibration readings</dt><dd>{numbers.format(home.calibration_rows)}</dd></div></dl>{home.baseline_end && <p className="file-hint">Baseline through {fullDate.format(new Date(home.baseline_end))}</p>}<p className="model-status">{home.model_status}</p><button className={home.household_id === activeId ? 'secondary-button' : 'primary-button'} onClick={() => onSelect(home.household_id)}>{home.household_id === activeId ? 'Open selected household →' : 'Select household →'}</button></article>)}</div>
    <section className="panel household-setup"><div><p className="eyebrow">ADD A HOUSEHOLD</p><h2>Learn a new pattern.</h2><p>Provide at least 14 days of representative, processed readings. Each row must contain the same household ID as this profile.</p><ul className="setup-notes"><li>At least 80% of the history must have complete inputs.</li><li>Earlier readings train the model; later readings set its alert threshold.</li><li>Use new readings afterward to see how it performs beyond its baseline.</li></ul><p className="file-hint">The CSV needs timestamp, litres_used, and household_id. A new profile does not inherit another household’s model.</p></div><form className="profile-form" onSubmit={create}><label htmlFor="household-name">Household name</label><input id="household-name" required maxLength={80} value={name} onChange={(event) => setName(event.target.value)} placeholder="Apartment 204" disabled={busy} /><label htmlFor="household-id">Household ID in your CSV</label><input id="household-id" required pattern="[a-zA-Z0-9][a-zA-Z0-9_-]{0,39}" maxLength={40} value={id} onChange={(event) => setId(event.target.value)} placeholder="hh-02" disabled={busy} /><label htmlFor="household-timezone">Household timezone</label><input id="household-timezone" required list="household-timezones" value={timezone} onChange={(event) => setTimezone(event.target.value)} disabled={busy} /><datalist id="household-timezones"><option value="Asia/Kolkata" /><option value="Europe/Berlin" /><option value="UTC" /><option value="America/New_York" /></datalist><label htmlFor="baseline-file">Baseline readings · CSV</label><input id="baseline-file" required type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] || null)} disabled={busy} />{error && <p className="inline-error" role="alert">{error}</p>}<button className="primary-button" disabled={busy || !file}>{busy ? 'Learning this household’s pattern…' : 'Create profile & learn baseline'}</button></form></section>
  </>
}
