import { dayReport, dateTime } from './analysis'

const escape = (value) => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;')
const safeName = (value) => String(value).replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 80)

function saveBlob(contents, filename, type) {
  const url = URL.createObjectURL(new Blob([contents], { type }))
  const link = document.createElement('a')
  link.href = url; link.download = filename
  document.body.appendChild(link); link.click(); link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function csvValue(value) {
  let text = String(value ?? '')
  // Keep free-text notes from becoming spreadsheet formulas when a report is opened.
  if (typeof value === 'string' && /^[\s]*[=+@\-\t\r]/.test(text)) text = "'" + text
  return `"${text.replaceAll('"', '""')}"`
}

function csv(rows) { return rows.map((row) => row.map(csvValue).join(',')).join('\r\n') }

export function downloadAnalysisCsv(result, day) {
  const readings = day ? result.readings.filter((row) => row.timestamp.startsWith(day)) : result.readings
  const rows = [['household_id', 'timestamp_utc', 'litres_used', 'anomaly_score', 'candidate', 'alert', 'analysis_id'], ...readings.map((row) => [result.household_id, row.timestamp, row.litres_used, row.anomaly_score, row.is_candidate, row.is_alert, result.analysis_id])]
  saveBlob(csv(rows), `leaklens-${safeName(result.household_id)}-${day || 'readings'}.csv`, 'text/csv;charset=utf-8')
}

export function downloadTicketCsv(ticket) {
  const rows = [['ticket_id', 'household_id', 'incident_id', 'status', 'finding', 'finding_note', 'repair_time_utc', 'followup_outcome', 'before_litres', 'after_litres', 'event_time_utc', 'event', 'event_note'], ...ticket.history.map((event) => [ticket.ticket_id, ticket.household_id, ticket.incident_id, ticket.status, ticket.finding?.outcome, ticket.finding?.note, ticket.repaired_at, ticket.verification?.outcome, ticket.verification?.before.recorded_litres, ticket.verification?.after.recorded_litres, event.at, event.action, event.note])]
  saveBlob(csv(rows), `leaklens-${safeName(ticket.ticket_id)}.csv`, 'text/csv;charset=utf-8')
}

function chartSvg(readings, day) {
  if (!readings.length) return ''
  const known = readings.filter((row) => Number.isFinite(row.litres_used))
  const max = Math.max(5, ...known.map((row) => row.litres_used))
  const start = Date.parse(`${day}T00:00:00Z`)
  const x = (row) => 50 + (Date.parse(row.timestamp) - start) / 86400000 * 700
  const y = (value) => 200 - value / max * 160
  const groups = []; let current = []
  for (const row of readings) {
    if (Number.isFinite(row.litres_used)) current.push(`${x(row)},${y(row.litres_used)}`)
    else if (current.length) { groups.push(current); current = [] }
  }
  if (current.length) groups.push(current)
  return `<svg viewBox="0 0 800 245" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Daily water consumption"><line x1="50" x2="750" y1="200" y2="200" stroke="#ccdcd4"/><text x="45" y="30" font-size="12">${max.toFixed(1)} L</text>${groups.map((points) => `<polyline fill="none" stroke="#14867e" stroke-width="2" points="${points.join(' ')}"/>`).join('')}${known.filter((row) => row.is_alert).map((row) => `<circle cx="${x(row)}" cy="${y(row.litres_used)}" r="3" fill="#d67a3c"/>`).join('')}${[0,6,12,18,24].map((hour) => `<text x="${50+hour/24*700}" y="225" text-anchor="middle" font-size="12">${String(hour).padStart(2,'0')}:00</text>`).join('')}</svg>`
}

function openReport(title, content) {
  const report = window.open('', '_blank')
  if (!report) throw new Error('Allow a report window to open, then try again.')
  report.opener = null
  report.document.write(`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${escape(title)}</title><style>body{font:14px system-ui;color:#234238;max-width:900px;margin:45px auto;padding:0 25px;line-height:1.6}h1{font-size:32px;letter-spacing:-1px}h2{font-size:20px;margin-top:30px}header{border-bottom:3px solid #14867e;padding-bottom:18px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:10px;border-bottom:1px solid #dde7df;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#f2f6ef}p,li{color:#526c5d}svg{width:100%;border:1px solid #dde7df;border-radius:10px}button{padding:12px 20px;background:#14867e;color:white;border:0;border-radius:6px;cursor:pointer}.note{padding:15px;background:#f2f6ef;border-left:3px solid #9dbca5}.toolbar{display:flex;gap:15px;align-items:center;margin-bottom:25px}.stats{display:flex;gap:20px;flex-wrap:wrap}.stats p{padding:15px;background:#f2f6ef;min-width:130px}.stats strong{display:block;font-size:24px}section{break-inside:avoid}@media print{.toolbar{display:none}body{margin:0;max-width:none;padding:0}a{color:inherit}thead{display:table-header-group}tr{break-inside:avoid}@page{margin:16mm}} </style></head><body><div class="toolbar"><button onclick="window.print()">Print / save as PDF</button><span>Choose “Save as PDF” in the print dialog.</span></div><header><strong>LeakLens · Water intelligence</strong><h1>${escape(title)}</h1><p>Generated ${escape(dateTime.format(new Date()))} UTC</p></header>${content}<p class="note">Suspected alerts require investigation. User-reported findings are separate from model predictions. Consumption changes do not establish water savings or prove a repaired leak.</p></body></html>`)
  report.document.close()
  report.focus()
}

export function printAnalysis(result, day) {
  const report = day ? dayReport(result, day) : null
  const incidents = report ? report.incidents : result.incidents
  const total = report ? report.total : result.summary.total_recorded_litres
  const valid = report ? report.valid.length : result.summary.valid_intervals
  const unknown = report ? report.unknown : result.summary.unknown_intervals
  const metadata = `<p>Household: <strong>${escape(result.household_name || result.household_id)}</strong> (${escape(result.household_id)}) · All times UTC</p><p>${escape(result.model_scope)}</p>${result.baseline_overlap ? '<p class="note">Some uploaded readings overlap the model baseline. This report is not an independent evaluation.</p>' : ''}`
  const summary = `<div class="stats"><p>Recorded use<strong>${total.toFixed(1)} L</strong></p><p>Suspected episodes<strong>${incidents.length}</strong></p><p>Valid intervals<strong>${valid}</strong></p><p>Unknown intervals<strong>${unknown}</strong></p></div>`
  const table = `<h2>Suspected episodes</h2><table><thead><tr><th>Episode</th><th>First / last alert · UTC</th><th>Observed evidence</th></tr></thead><tbody>${incidents.map((incident) => `<tr><td>${escape(incident.incident_id)}</td><td>${escape(incident.first_alert_at)}<br>${escape(incident.last_alert_at)}</td><td>${(incident.explanation?.reasons || ['Reanalyse this file to include alert evidence.']).map(escape).join('<br>')}</td></tr>`).join('')}</tbody></table>`
  const plot = report ? `<section><h2>Water use on ${escape(day)}</h2>${chartSvg(report.readings, day)}<p>Litres per 15-minute interval. Orange points are alerts; gaps are unknown readings. Daily coverage: ${valid}/96 intervals. ${report.outsideUpload} intervals are outside the uploaded period.</p></section>` : ''
  openReport(day ? `Daily report · ${day}` : 'Water-use analysis', metadata + summary + table + plot)
}

export function printTicket(ticket) {
  const finding = ticket.finding
  const follow = ticket.verification
  const content = `<p>Ticket: ${escape(ticket.ticket_id)}<br>Household: ${escape(ticket.household_id)}<br>Episode: ${escape(ticket.incident_id)}<br>Status: ${escape(ticket.status === 'repaired' ? 'Repair reported' : ticket.status)}</p><h2>Investigation finding</h2><p>${finding ? `${escape(finding.outcome.replaceAll('_',' '))} · user reported<br>${escape(finding.note)}` : 'No finding recorded yet.'}</p><h2>Reported repair</h2><p>${escape(ticket.repaired_at || 'No repair reported.')}</p>${follow ? `<section><h2>Follow-up comparison</h2><p>${escape(follow.message)}</p><table><tr><th>Window</th><th>Recorded litres</th><th>Valid intervals</th><th>Alert intervals</th></tr><tr><td>24 hours before</td><td>${follow.before.recorded_litres}</td><td>${follow.before.valid_intervals}/96</td><td>${follow.before.alert_intervals}</td></tr><tr><td>24 hours after</td><td>${follow.after.recorded_litres}</td><td>${follow.after.valid_intervals}/96</td><td>${follow.after.alert_intervals}</td></tr></table><p>${escape(follow.limitation)}</p></section>` : ''}<h2>Activity history</h2><table><thead><tr><th>Time · UTC</th><th>Action</th><th>Note</th></tr></thead><tbody>${ticket.history.map((event) => `<tr><td>${escape(event.at)}</td><td>${escape(event.action.replaceAll('_',' '))}</td><td>${escape(event.note)}</td></tr>`).join('')}</tbody></table>`
  openReport('Maintenance report', content)
}
