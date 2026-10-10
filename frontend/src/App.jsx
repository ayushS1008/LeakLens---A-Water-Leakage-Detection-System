import { useEffect, useRef, useState } from 'react'
import './App.css'
import Maintenance from './Maintenance'
import ConsumptionChart from './ConsumptionChart'
import DayDetails from './DayDetails'
import Households from './Households'
import Notifications from './Notifications'
import useNotifications from './useNotifications'
import AlertExplanation from './AlertExplanation'
import ReportActions from './ReportActions'
import { apiRequest } from './api'
import { availableDays, dateTime, dayReport, fullDate, numbers } from './analysis'
import { navigate, pageLink, readRoute } from './navigation'

function rememberAnalysis(id, household = 'hh-01') {
  try { const key = `leaklens-analysis-${household}`; if (id) sessionStorage.setItem(key, id); else { sessionStorage.removeItem(key); if (household === 'hh-01') sessionStorage.removeItem('leaklens-analysis') } } catch { /* The current page still works without browser storage. */ }
}
function previousAnalysis(household = 'hh-01') {
  try { return sessionStorage.getItem(`leaklens-analysis-${household}`) || (household === 'hh-01' ? sessionStorage.getItem('leaklens-analysis') : null) } catch { return null }
}
function previousHousehold() { try { return localStorage.getItem('leaklens-household') || 'hh-01' } catch { return 'hh-01' } }
function rememberHousehold(id) { try { localStorage.setItem('leaklens-household', id) } catch { /* Selection works for this session. */ } }

function checkAnalysis(body) {
  if (!body.summary || !Array.isArray(body.readings) || !body.readings.length || !Array.isArray(body.incidents) || !body.analysis_id) {
    throw new Error('The analysis response is incomplete. Check the backend, then upload your CSV again.')
  }
  return body
}

function NoAnalysis({ title = 'Your readings come first.' }) {
  return <section className="panel empty-state"><span className="empty-symbol" aria-hidden="true">⌁</span><h2>{title}</h2><p>Upload a processed CSV on Overview to explore water use and suspected episodes.</p><a className="primary-button button-link" href={pageLink('overview')}>Go to Overview →</a></section>
}

function App() {
  const inbox = useNotifications()
  const [households, setHouseholds] = useState([])
  const [activeId, setActiveId] = useState(previousHousehold)
  const [profileRefresh, setProfileRefresh] = useState(0)
  const [profileError, setProfileError] = useState('')
  const [route, setRoute] = useState(readRoute)
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [selectedDay, setSelectedDay] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(null)
  const [loading, setLoading] = useState(false)
  const [restoring, setRestoring] = useState(Boolean(previousAnalysis(previousHousehold()) || readRoute().analysis))
  const [connection, setConnection] = useState('checking')
  const [connectionAttempt, setConnectionAttempt] = useState(0)
  const [tickets, setTickets] = useState([])
  const [storage, setStorage] = useState('')
  const [ticketError, setTicketError] = useState('')
  const [ticketLoading, setTicketLoading] = useState(true)
  const [ticketRefresh, setTicketRefresh] = useState(0)
  const [ticketBusy, setTicketBusy] = useState('')
  const [ticketFilter, setTicketFilter] = useState('all')
  const restoreController = useRef(null)

  useEffect(() => {
    function changed() { const next = readRoute(); if (next.analysis) { setResult(null); setRestoring(true) }; setRoute(next); window.scrollTo({ top: 0, behavior: 'instant' }) }
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    apiRequest('/health', { signal: controller.signal }).then((body) => {
      if (!controller.signal.aborted) setConnection(body.model_loaded ? 'connected' : 'offline')
    }).catch(() => { if (!controller.signal.aborted) setConnection('offline') })
    return () => controller.abort()
  }, [connectionAttempt])

  useEffect(() => {
    const controller = new AbortController()
    apiRequest('/households', { signal: controller.signal }).then((body) => { setHouseholds(body.households); setProfileError('') })
      .catch((failure) => { if (!controller.signal.aborted) setProfileError(failure.message) })
    return () => controller.abort()
  }, [profileRefresh])

  useEffect(() => {
    const id = route.analysis || previousAnalysis(activeId)
    if (!id) return
    const controller = new AbortController()
    restoreController.current = controller
    apiRequest(`/analyses/${encodeURIComponent(id)}`, { signal: controller.signal }).then(checkAnalysis).then((body) => {
      if (controller.signal.aborted) return
      setResult(body)
      setActiveId(body.household_id)
      rememberHousehold(body.household_id)
      rememberAnalysis(body.analysis_id, body.household_id)
      setSelectedDay((body.incidents[0]?.first_alert_at ?? body.readings[0].timestamp).slice(0, 10))
      setError('')
    }).catch((failure) => {
      if (controller.signal.aborted) return
      if (failure.status === 404) rememberAnalysis(null, activeId)
      setError(`Could not restore this analysis. ${failure.message}`)
    }).finally(() => { if (!controller.signal.aborted) setRestoring(false) })
    return () => controller.abort()
  }, [activeId, route.analysis])

  function selectHousehold(id) {
    if (loading) return
    if (id === activeId) { navigate('overview'); return }
    restoreController.current?.abort()
    rememberHousehold(id)
    setActiveId(id); setResult(null); setFile(null); setNotice(null); setError('')
    setRestoring(Boolean(previousAnalysis(id)))
    navigate('overview')
  }

  useEffect(() => {
    const controller = new AbortController()
    apiRequest('/tickets', { signal: controller.signal }).then((body) => {
      if (controller.signal.aborted) return
      setTickets(body.tickets)
      setStorage(body.storage)
      setTicketError('')
    }).catch((failure) => { if (!controller.signal.aborted) setTicketError(failure.message) })
      .finally(() => { if (!controller.signal.aborted) setTicketLoading(false) })
    return () => controller.abort()
  }, [ticketRefresh])

  async function createTicket(incident) {
    setTicketBusy(incident.incident_id)
    setTicketError('')
    try {
      const ticket = await apiRequest('/tickets', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_id: result.analysis_id, incident_id: incident.incident_id }),
      })
      if (!ticket.ticket_id) throw new Error('The server did not return a ticket. Please refresh and try again.')
      setTickets((current) => [ticket, ...current.filter((item) => item.ticket_id !== ticket.ticket_id)])
      setNotice({ ticketId: ticket.ticket_id, message: `Ticket ready for ${ticket.incident_id}. Its details are open below.` })
      navigate('maintenance', { ticket: ticket.ticket_id })
    } catch (failure) {
      setTicketError(`Could not create a ticket for ${incident.incident_id}. ${failure.message}`)
    } finally {
      setTicketBusy('')
    }
  }

  async function analyse(event) {
    event.preventDefault()
    if (!file || loading) return
    setError('')
    setNotice(null)
    if (!file.name.toLowerCase().endsWith('.csv')) { setError('Choose a CSV file.'); return }
    if (file.size > 10 * 1024 * 1024) { setError('The maximum file size is 10 MB.'); return }
    restoreController.current?.abort()
    setRestoring(false)
    setLoading(true)
    const form = new FormData()
    form.append('file', file)
    try {
      const body = checkAnalysis(await apiRequest(`/analyse?include_readings=true&household_id=${encodeURIComponent(activeId)}`, { method: 'POST', body: form }))
      setResult(body)
      rememberAnalysis(body.analysis_id, body.household_id)
      inbox.refresh()
      setSelectedDay((body.incidents[0]?.first_alert_at ?? body.readings[0].timestamp).slice(0, 10))
      setConnection('connected')
      setTicketRefresh((value) => value + 1)
    } catch (failure) {
      setError(failure.message)
    } finally {
      setLoading(false)
    }
  }

  function refreshTickets() { setTicketLoading(true); setTicketRefresh((value) => value + 1) }
  function ticketChanged(updated) { setTickets((current) => current.map((ticket) => ticket.ticket_id === updated.ticket_id ? updated : ticket)) }
  const days = availableDays(result)
  const chartDay = days.includes(selectedDay) ? selectedDay : days[0]
  const dayIndex = days.indexOf(chartDay)
  const daily = result ? dayReport(result, chartDay) : null
  const summary = result?.summary
  const savedTickets = new Map(tickets.filter((ticket) => ticket.analysis_id === result?.analysis_id).map((ticket) => [ticket.incident_id, ticket]))
  const filteredIncidents = result?.incidents.filter((incident) => ticketFilter === 'all' || (ticketFilter === 'saved' ? savedTickets.has(incident.incident_id) : !savedTickets.has(incident.incident_id))) ?? []
  const householdTickets = tickets.filter((ticket) => ticket.household_id === activeId)
  const navItems = [['overview', 'Overview'], ['alerts', 'Alerts'], ['maintenance', 'Maintenance'], ['day', 'Day details'], ['households', 'Households'], ['notifications', 'Notifications']]

  return (
    <div className="dashboard">
      <header className="topbar"><a className="brand" href={pageLink('overview')} aria-label="LeakLens home"><span className="brand-symbol" aria-hidden="true">◉</span>LeakLens<span className="brand-tag">Water intelligence</span></a><div className="connection-controls"><label className="household-switch">Household<select aria-label="Active household" value={activeId} disabled={loading || !households.length} onChange={(event) => selectHousehold(event.target.value)}>{households.length ? households.map((household) => <option key={household.household_id} value={household.household_id}>{household.name}</option>) : <option value={activeId}>{activeId}</option>}</select></label><span className={`connection ${connection}`} role="status"><span aria-hidden="true" />{connection === 'connected' ? 'API connected' : connection === 'checking' ? 'Checking API…' : 'API unavailable'}</span>{connection === 'offline' && <button className="text-button" onClick={() => { setConnection('checking'); setConnectionAttempt((attempt) => attempt + 1) }}>Retry connection</button>}</div></header>
      <nav className="page-nav" aria-label="Main navigation">{navItems.map(([page, label]) => <a key={page} href={pageLink(page, page === 'day' ? { date: route.date || chartDay } : {})} aria-current={route.page === page ? 'page' : undefined}><span>{label}</span>{page === 'alerts' && summary && <span className="nav-count">{summary.alert_episodes}</span>}{page === 'maintenance' && householdTickets.length > 0 && <span className="nav-count">{householdTickets.length}</span>}{page === 'notifications' && inbox.unread_count > 0 && <span className="nav-count notification-count">{inbox.unread_count}</span>}</a>)}</nav>
      <main>
        {profileError && <div className="error-message" role="alert">Could not load households. {profileError}<button className="text-button" onClick={() => setProfileRefresh((value) => value + 1)}>Retry</button></div>}
        {restoring && <p className="progress-message" role="status">Restoring your last analysis…</p>}
        {route.page !== 'overview' && error && <div className="error-message" role="alert">{error}</div>}
        {route.page === 'overview' && <>
          <div className="page-heading"><p className="eyebrow">WATER CONSUMPTION{result ? ` · ${result.household_id}` : ''}</p><h1>Every drop tells a story.</h1><p>See your water use clearly. Find persistent patterns worth investigating.</p></div>
          <section className="panel upload-panel" aria-labelledby="upload-title"><div><p className="eyebrow">ANALYSE READINGS</p><h2 id="upload-title">Start with your meter data</h2><p>Upload one household’s processed 15-minute readings to explore consumption and suspected leaks.</p><div className="upload-meta"><span>CSV format</span><span>Up to 10 MB</span><span>25,000 intervals</span></div><details className="format-help"><summary>Which file should I use?</summary><p>For the household dataset, choose <code>hh01_15min.csv</code>. Your CSV needs <code>timestamp</code> and <code>litres_used</code> columns. Include <code>household_id</code> on every row, matching the selected household. Add other households on the Households page.</p></details></div><form onSubmit={analyse} className="upload-form"><label htmlFor="csv-upload">Processed CSV file</label><input key={activeId} id="csv-upload" type="file" accept=".csv,text/csv" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setError('') }} disabled={loading} /><button className="primary-button" type="submit" disabled={!file || loading}>{loading ? 'Analysing readings…' : 'Analyse water use →'}</button></form></section>
          {error && <div className="error-message" role="alert">{error}</div>}
          {loading && <p className="progress-message" role="status">The model is checking your readings. Your new results will appear here.</p>}
          {result && !loading ? <>
            {result.baseline_overlap && <p className="baseline-note">Some uploaded readings overlap this model’s training or calibration period. These results are exploratory, not an independent evaluation.</p>}
            <ReportActions result={result} />
            <div className="dataset-strip"><span><i aria-hidden="true" />Analysis ready · <strong>{result.household_id}</strong></span><span>{fullDate.format(new Date(result.readings[0].timestamp))} – {fullDate.format(new Date(result.readings.at(-1).timestamp))}</span></div>
            <section className="metrics" aria-label="Analysis summary"><article className="metric"><p>Recorded consumption</p><strong>{numbers.format(summary.total_recorded_litres)} <small>L</small></strong><span>Across the uploaded period</span></article><article className="metric alert-metric"><p>Suspected leak episodes</p><strong>{summary.alert_episodes}</strong><a href={pageLink('alerts')}>Review alerts ↗</a></article><article className="metric"><p>Valid intervals</p><strong>{numbers.format(summary.valid_intervals)}</strong><span>Of {numbers.format(summary.total_intervals)} intervals</span></article><article className="metric"><p>Unknown intervals</p><strong>{summary.unknown_intervals}</strong><span>Excluded from consumption totals</span></article></section>
            <section className="panel chart-panel" aria-labelledby="chart-title"><div className="section-heading"><div><p className="eyebrow">EXPLORE THE PATTERN</p><h2 id="chart-title">Daily water use</h2><p>Litres per 15-minute interval · UTC</p></div><div className="day-controls"><button aria-label="Previous day" disabled={dayIndex <= 0} onClick={() => setSelectedDay(days[dayIndex - 1])}>←</button><label className="visually-hidden" htmlFor="chart-day">Chart date (UTC)</label><input id="chart-day" type="date" min={days[0]} max={days.at(-1)} value={chartDay} onChange={(event) => { if (days.includes(event.target.value)) setSelectedDay(event.target.value) }} /><button aria-label="Next day" disabled={dayIndex >= days.length - 1} onClick={() => setSelectedDay(days[dayIndex + 1])}>→</button></div></div><ConsumptionChart readings={daily.readings} day={chartDay} /><div className="chart-footer"><div className="legend"><span><i className="water-dot" />Recorded water use</span><span><i className="alert-dot" />Alert interval</span></div><a className="text-button" href={pageLink('day', { date: chartDay })}>Full day report ↗</a><p>{numbers.format(daily.total)} L recorded · {daily.unknown} unknown intervals</p></div></section>
            <aside className="analysis-note"><strong>Patterns, followed by action.</strong><p>{result.model_scope} Alerts mark persistent unusual flow and need investigation. Missing readings are not scored. These results do not confirm a leak or measure water saved.</p><div className="note-actions"><a href={pageLink('alerts')}>Explore alerts →</a><a href={pageLink('maintenance')}>Open maintenance →</a></div></aside>
          </> : !loading && !restoring && <div className="empty-state"><span className="empty-symbol" aria-hidden="true">⌁</span><h2>Your water story starts here.</h2><p>Your summary and daily chart will appear here after you analyse a CSV.</p></div>}
        </>}
        {route.page === 'alerts' && <>
          <div className="page-heading"><p className="eyebrow">REVIEW ALERTS</p><h1>Know where to look.</h1><p>Investigate persistent unusual use, review its day, and turn an alert into a maintenance ticket.</p></div>
          {!result ? <NoAnalysis /> : <>
            <div className="alert-overview"><div><strong>{summary.alert_episodes}</strong><p>Suspected episodes</p></div><div><strong>{savedTickets.size}</strong><p>With saved tickets</p></div><div><strong>{result.household_id}</strong><p>Household analysed</p></div><p>Alerts are a reason to investigate. Ordinary household activities can also trigger them.</p></div>
            {ticketError && <div className="error-message" role="alert">{ticketError}<button className="text-button" onClick={refreshTickets}>Refresh tickets</button></div>}
            <section className="panel" aria-labelledby="alerts-title"><div className="section-heading"><div><p className="eyebrow">SUSPECTED PATTERNS</p><h2 id="alerts-title">Episodes to review</h2><p>First and last alert times · UTC</p></div><div className="filter-control"><label htmlFor="ticket-filter">Show</label><select id="ticket-filter" value={ticketFilter} onChange={(event) => setTicketFilter(event.target.value)}><option value="all">All episodes</option><option value="new">Without a ticket</option><option value="saved">With a ticket</option></select></div></div>
              {filteredIncidents.length ? <div className="table-wrap"><table><thead><tr><th>Episode</th><th>First alert · UTC</th><th>Last alert · UTC</th><th>Flagged intervals</th><th>Ticket</th><th>Actions</th></tr></thead><tbody>{filteredIncidents.map((incident) => {
                const ticket = savedTickets.get(incident.incident_id)
                return <tr key={incident.incident_id}><td className="episode-id">{incident.incident_id}<AlertExplanation explanation={incident.explanation} compact /></td><td>{dateTime.format(new Date(incident.first_alert_at))}</td><td>{dateTime.format(new Date(incident.last_alert_at))}</td><td>{incident.alert_intervals}</td><td><span className={`status-badge ${ticket ? 'ticket-saved' : ''}`}>{ticket ? ticket.status === 'repaired' ? 'Repair reported' : ticket.status === 'investigating' ? 'Investigating' : 'Open' : 'Not created'}</span></td><td><div className="episode-actions"><a className="text-button" href={pageLink('day', { date: incident.first_alert_at.slice(0, 10) })}>View day ↗</a>{ticket ? <a className="small-button" href={pageLink('maintenance', { ticket: ticket.ticket_id })}>Open ticket →</a> : <button className="small-button" disabled={Boolean(ticketBusy) || ticketLoading} onClick={() => createTicket(incident)}>{ticketBusy === incident.incident_id ? 'Creating…' : 'Create ticket'}</button>}</div></td></tr>
              })}</tbody></table></div> : <div className="empty-alerts"><h3>{result.incidents.length ? 'No episodes match this filter.' : 'No suspected episodes in this upload.'}</h3><p>{result.incidents.length ? 'Choose another filter to see your other episodes.' : 'No persistent unusual pattern met the detector’s criteria.'}</p></div>}
            </section>
          </>}
        </>}
        {route.page === 'maintenance' && <>
          <div className="page-heading"><p className="eyebrow">MAINTENANCE & FOLLOW-UP</p><h1>Follow through on the finding.</h1><p>Keep a record of what was checked, report a repair, and review the next day’s readings.</p></div>
          {notice?.ticketId === route.ticket && <div className="action-notice" role="status"><span aria-hidden="true">✓</span>{notice.message}</div>}
          <Maintenance tickets={householdTickets} storage={storage} selectedId={route.ticket} error={ticketError} loading={ticketLoading} onRefresh={refreshTickets} onChanged={ticketChanged} />
        </>}
        {route.page === 'day' && <DayDetails key={`${route.date}:${result?.analysis_id || ''}`} result={result} date={route.date} />}
        {route.page === 'households' && <Households households={households} activeId={activeId} onSelect={selectHousehold} onCreated={(profile) => { setHouseholds((current) => [...current.filter((item) => item.household_id !== profile.household_id), profile]); setProfileRefresh((value) => value + 1) }} />}
        {route.page === 'notifications' && <Notifications inbox={inbox} />}
      </main>
      <footer><span className="footer-brand">LeakLens</span><span>Water-consumption anomaly detection prototype · All display times in UTC</span></footer>
    </div>
  )
}

export default App
