import AlertExplanation from './AlertExplanation'
import ReportActions from './ReportActions'
import { useState } from 'react'
import { apiRequest } from './api'
import { dateTime, numbers } from './analysis'
import { pageLink } from './navigation'

const findings = { confirmed_leak: 'Confirmed leak', normal_activity: 'Normal activity', undetermined: 'Undetermined' }

const labels = { open: 'Open', investigating: 'Investigating', repaired: 'Repair reported' }
const outcomes = { improved: 'Follow-up improved', alerts_persist: 'Alerts persist', insufficient_data: 'Insufficient data', inconclusive: 'Inconclusive' }

function TicketDetails({ ticket, onChanged }) {
  const [finding, setFinding] = useState(ticket.finding?.outcome || 'undetermined')
  const [findingNote, setFindingNote] = useState(ticket.finding?.note || '')
  const [repairTime, setRepairTime] = useState(ticket.repaired_at?.slice(0, 16) ?? '')
  const [note, setNote] = useState('')
  const [followup, setFollowup] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function update(status) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const updated = await apiRequest(`/tickets/${ticket.ticket_id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, revision: ticket.revision, note, repaired_at: status === 'repaired' ? `${repairTime}:00Z` : null }),
      })
      onChanged(updated)
      setMessage(status === 'repaired' ? 'Repair report saved. Upload follow-up readings to check the change.' : 'Investigation started. Your note has been saved.')
      setNote('')
    } catch (failure) { setError(failure.message) } finally { setBusy(false) }
  }

  async function saveFinding(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      onChanged(await apiRequest(`/tickets/${ticket.ticket_id}/finding`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ outcome: finding, note: findingNote, revision: ticket.revision }) }))
      setMessage('Investigation finding saved. This records your report; the model prediction is unchanged.')
    } catch (failure) { setError(failure.message) } finally { setBusy(false) }
  }

  async function verify(event) {
    event.preventDefault()
    if (!followup) return
    setBusy(true)
    setError('')
    setMessage('')
    const form = new FormData()
    form.append('file', followup)
    form.append('revision', String(ticket.revision))
    try { onChanged(await apiRequest(`/tickets/${ticket.ticket_id}/verify`, { method: 'POST', body: form })); setMessage('Follow-up checked. Your comparison is saved below.') }
    catch (failure) { setError(failure.message) } finally { setBusy(false) }
  }

  const report = ticket.verification
  return (
    <article className="panel ticket-details" aria-labelledby="ticket-title">
      <div className="section-heading"><div><p className="eyebrow">SELECTED TICKET</p><h2 id="ticket-title">{ticket.incident_id}</h2><p>{ticket.household_id} · first alert {dateTime.format(new Date(ticket.first_alert_at))} UTC</p></div><span className={`status-badge ticket-status ${ticket.status}`}>{labels[ticket.status]}</span></div>
      <ReportActions ticket={ticket} /><AlertExplanation explanation={ticket.explanation} />
      <p>{ticket.description}</p><p className="ticket-reference">Reference: {ticket.ticket_id}</p>
      <div className="workflow-progress" aria-label="Ticket progress">{[['open', 'Open'], ['investigating', 'Investigating'], ['repaired', 'Repair reported']].map(([status, label], index) => <span key={status} className={index <= ['open', 'investigating', 'repaired'].indexOf(ticket.status) ? 'complete' : ''}><i aria-hidden="true" />{label}</span>)}</div>
      {error && <div className="error-message" role="alert">{error}</div>}
      {message && <div className="action-notice compact" role="status">{message}</div>}
      <section className="finding-section"><p className="eyebrow">HUMAN REVIEW</p><h3>What did the investigation find?</h3><p>Record what you checked, even when the alert was normal activity.</p>{ticket.finding && <div className="finding-record"><strong>{findings[ticket.finding.outcome]} · user reported</strong><p>{ticket.finding.note}</p><small>{dateTime.format(new Date(ticket.finding.recorded_at))} UTC</small></div>}<form onSubmit={saveFinding}><label htmlFor="finding-outcome">Investigation outcome</label><select id="finding-outcome" value={finding} disabled={busy} onChange={(event) => setFinding(event.target.value)}>{Object.entries(findings).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><label htmlFor="finding-note">What did you observe?</label><textarea id="finding-note" value={findingNote} onChange={(event) => setFindingNote(event.target.value)} required maxLength={1000} rows={3} disabled={busy} placeholder="Describe the inspection or activity that explains the readings." /><button className="secondary-button" disabled={busy || !findingNote.trim()}>{busy ? 'Saving…' : 'Save finding'}</button></form><p className="file-hint">Findings are saved separately from suspected alerts. They do not automatically retrain the model.</p></section>
      {ticket.status !== 'repaired'  && <form className="repair-form" onSubmit={(event) => { event.preventDefault(); update('repaired') }}>
        <label htmlFor="repair-note">Investigation / repair note</label><textarea id="repair-note" value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} rows={3} disabled={busy} placeholder="What did you check? What was repaired?" />
        {ticket.status === 'open' && <button type="button" className="secondary-button" disabled={busy} onClick={() => update('investigating')}>{busy ? 'Saving…' : 'Start investigating'}</button>}
        <div className="form-divider" /><label htmlFor="repair-time">Reported repair time · UTC</label><input id="repair-time" type="datetime-local" step="900" required value={repairTime} onChange={(event) => setRepairTime(event.target.value)} disabled={busy} />
        <p className="file-hint">Enter the time represented by the readings, in 15-minute steps. Reporting a repair records your update; it does not confirm that a leak is fixed.</p>
        <button type="submit" className="primary-button" disabled={busy || !repairTime}>{busy ? 'Saving…' : 'Report repair'}</button>
      </form>}
      {ticket.status === 'repaired' && <form className="repair-form" onSubmit={verify}><div className="repair-record"><span aria-hidden="true">✓</span><p>Repair reported<br /><strong>{dateTime.format(new Date(ticket.repaired_at))} UTC</strong></p></div><label htmlFor="followup-upload">Follow-up processed CSV</label><input id="followup-upload" type="file" accept=".csv,text/csv" onChange={(event) => setFollowup(event.target.files?.[0] ?? null)} disabled={busy} /><p className="file-hint">Include the 24 hours after repair and one hour of preceding context. Both comparison windows need complete, scored readings.</p><button className="primary-button" type="submit" disabled={busy || !followup}>{busy ? 'Checking follow-up…' : 'Check follow-up readings'}</button></form>}
      {report && <div className={`verification-result ${report.outcome}`} role="status"><p className="eyebrow">FOLLOW-UP RESULT</p><h3>{outcomes[report.outcome]}</h3><p>{report.message}</p><div className="verification-metrics"><div><span>24 hours before</span><strong>{numbers.format(report.before.recorded_litres)} <small>L</small></strong><p>{report.before.valid_intervals}/96 valid intervals · {report.before.alert_intervals} alert intervals</p></div><div><span>24 hours after</span><strong>{numbers.format(report.after.recorded_litres)} <small>L</small></strong><p>{report.after.valid_intervals}/96 valid intervals · {report.after.alert_intervals} alert intervals</p></div></div>{report.consumption_change_percent !== null && <p>Recorded consumption change: <strong>{numbers.format(report.consumption_change_percent)}%</strong>.</p>}<p className="file-hint">{report.limitation}</p></div>}
      <details className="ticket-history"><summary>Activity history <span>{ticket.history.length} updates</span></summary><ol>{ticket.history.map((item, index) => <li key={index}><strong>{item.action.replaceAll('_', ' ')}</strong><time>{dateTime.format(new Date(item.at))} UTC</time>{item.note && <p>{item.note}</p>}</li>)}</ol></details>
    </article>
  )
}

export default function Maintenance({ tickets, storage, selectedId, error, loading, onRefresh, onChanged }) {
  const selected = selectedId ? tickets.find((ticket) => ticket.ticket_id === selectedId) : tickets[0]
  return <>
    <div className="maintenance-toolbar"><p>{storage && <><span className="storage-dot" aria-hidden="true" />Saved in {storage}</>}</p><button className="secondary-button" disabled={loading} onClick={onRefresh}>{loading ? 'Refreshing…' : 'Refresh tickets'}</button></div>
    {error && <div className="error-message" role="alert">{error}</div>}
    {tickets.length ? <div className="maintenance-grid"><aside className="ticket-sidebar"><div className="ticket-list-heading"><h2>Saved tickets</h2><span className="count-badge">{tickets.length}</span></div><div className="ticket-list" aria-label="Saved maintenance tickets">{tickets.map((ticket) => <a className={`ticket-card ${selected?.ticket_id === ticket.ticket_id ? 'selected' : ''}`} key={ticket.ticket_id} href={pageLink('maintenance', { ticket: ticket.ticket_id })} aria-current={selected?.ticket_id === ticket.ticket_id ? 'true' : undefined}><div><strong>{ticket.incident_id}</strong><span className={`ticket-dot ${ticket.status}`} aria-hidden="true" /></div><span>{ticket.household_id} · {labels[ticket.status]}</span><small>{dateTime.format(new Date(ticket.first_alert_at))} UTC</small>{ticket.finding && <span className="ticket-outcome">{findings[ticket.finding.outcome]} · reported</span>}{ticket.verification && <span className="ticket-outcome">{outcomes[ticket.verification.outcome]}</span>}</a>)}</div></aside>{selected ? <TicketDetails key={selected.ticket_id} ticket={selected} onChanged={onChanged} /> : <div className="panel empty-state"><h2>This ticket is unavailable.</h2><p>Choose a saved ticket or refresh the list.</p></div>}</div> : !loading && !error ? <section className="panel empty-state"><span className="empty-symbol" aria-hidden="true">⌁</span><h2>A place for every investigation.</h2><p>Create a ticket from an alert to track an investigation, report a repair, and review follow-up readings.</p><a className="primary-button button-link" href={pageLink('alerts')}>Review alerts →</a></section> : loading && <p className="progress-message" role="status">Loading saved tickets…</p>}
  </>
}
