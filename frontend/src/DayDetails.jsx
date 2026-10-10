import { useState } from 'react'
import AlertExplanation from './AlertExplanation'
import ReportActions from './ReportActions'
import ConsumptionChart from './ConsumptionChart'
import { availableDays, dayReport, fullDate, numbers, shortTime, dateTime } from './analysis'
import { navigate, pageLink } from './navigation'

export default function DayDetails({ result, date }) {
  const days = availableDays(result)
  const chosen = date || days[0]
  const [draft, setDraft] = useState(chosen || '')
  const [error, setError] = useState('')
  const report = result && days.includes(chosen) ? dayReport(result, chosen) : null

  function showDay(event) {
    event.preventDefault()
    if (!days.includes(draft)) {
      setError('This date is outside the uploaded readings. Choose a day within the available range.')
      return
    }
    setError('')
    navigate('day', { date: draft })
  }

  return (
    <>
      <div className="page-heading"><p className="eyebrow">DAY DETAILS</p><h1>A closer look at one day.</h1><p>Choose a date to understand its consumption, data coverage, and alert patterns.</p></div>
      {!result ? <div className="panel empty-state"><h2>Start with an analysis</h2><p>Upload your readings on Overview to explore a specific day.</p><a className="primary-button button-link" href={pageLink('overview')}>Go to Overview →</a></div> : <>
        <section className="panel date-panel">
          <div><h2>Which day would you like to review?</h2><p>Available {fullDate.format(new Date(`${days[0]}T00:00:00Z`))} – {fullDate.format(new Date(`${days.at(-1)}T00:00:00Z`))} · UTC</p></div>
          <form className="date-form" onSubmit={showDay}><label htmlFor="report-date">Enter a date · UTC</label><div><input id="report-date" type="date" min={days[0]} max={days.at(-1)} required value={draft} onChange={(event) => setDraft(event.target.value)} /><button className="primary-button" type="submit">Show day</button></div></form>
          {error && <p className="inline-error" role="alert">{error}</p>}
        </section>
        {!report ? <div className="error-message" role="alert">No readings are available for this date. Select a date in the uploaded range.</div> : <>
          <div className="report-heading"><div><p className="eyebrow">DAILY REPORT · {result.household_id}</p><h2>{fullDate.format(new Date(`${chosen}T00:00:00Z`))}</h2></div><span className={`report-status ${report.alerts.length ? 'has-alerts' : ''}`}>{report.alerts.length ? 'Patterns to investigate' : 'No alerts recorded'}</span></div>
          <ReportActions result={result} day={chosen} />
          <section className="metrics" aria-label="Daily summary">
            <article className="metric"><p>Recorded consumption</p><strong>{numbers.format(report.total)} <small>L</small></strong><span>Known readings on this day</span></article>
            <article className="metric"><p>Suspected episodes</p><strong>{report.incidents.length}</strong><span>Episodes overlapping this day</span></article>
            <article className="metric"><p>Peak interval use</p><strong>{report.peak ? numbers.format(report.peak.litres_used) : '—'} <small>{report.peak ? 'L' : ''}</small></strong><span>{report.peak ? `Interval ending ${shortTime.format(new Date(report.peak.timestamp))} UTC` : 'No usable consumption readings'}</span></article>
            <article className="metric"><p>Data coverage</p><strong>{numbers.format(report.valid.length / 96 * 100)}<small>%</small></strong><span>{report.valid.length} of 96 daily intervals valid</span></article>
          </section>
          <section className="panel day-context"><div><p className="eyebrow">READING THE DAY</p><h2>What the readings tell us</h2><p>{report.alerts.length ? `${report.alerts.length} ${report.alerts.length === 1 ? 'interval triggered an alert' : 'intervals triggered alerts'}. Review the periods below and check whether the household's activities explain the use.` : 'No intervals met the alert criteria on this day. This does not prove that the household has no leak.'}</p></div><dl className="day-facts">
            <div><dt>Intervals with water use</dt><dd>{report.positive}</dd></div><div><dt>Zero recorded consumption</dt><dd>{report.zero}</dd></div>
            <div><dt>Unknown within upload</dt><dd>{report.unknown}</dd></div><div><dt>Outside uploaded time range</dt><dd>{report.outsideUpload}</dd></div>
            <div><dt>Intervals scored by the model</dt><dd>{report.scored.length}</dd></div><div><dt>Alert intervals</dt><dd>{report.alerts.length}</dd></div>
          </dl><p className="file-hint">Each interval covers 15 minutes. A complete UTC day has 96 intervals. Missing readings are never counted as zero use.</p></section>
          <section className="panel" aria-labelledby="day-alerts-title"><div className="section-heading"><div><p className="eyebrow">RELATED ALERTS</p><h2 id="day-alerts-title">Episodes on this day</h2></div><a className="text-button" href={pageLink('alerts')}>Review all alerts ↗</a></div>
            {report.incidents.length ? <div className="day-episodes">{report.incidents.map((incident) => <article key={incident.incident_id}><div><strong>{incident.incident_id}</strong><p>{dateTime.format(new Date(incident.first_alert_at))} – {dateTime.format(new Date(incident.last_alert_at))} UTC</p><AlertExplanation explanation={incident.explanation} /></div><span className="status-badge">Suspected</span></article>)}</div> : <p>No suspected episodes overlap this day.</p>}
          </section>
          <section className="panel chart-panel" aria-labelledby="report-chart-title"><div className="section-heading"><div><p className="eyebrow">THE DAILY PATTERN</p><h2 id="report-chart-title">Water use throughout the day</h2><p>Litres per 15-minute interval · UTC</p></div></div><ConsumptionChart readings={report.readings} day={chosen} /><div className="chart-footer"><div className="legend"><span><i className="water-dot" />Recorded water use</span><span><i className="alert-dot" />Alert interval</span></div><p>{numbers.format(report.total)} L recorded · {report.unknown} unknown intervals within upload</p></div></section>
        </>}
      </>}
    </>
  )
}
