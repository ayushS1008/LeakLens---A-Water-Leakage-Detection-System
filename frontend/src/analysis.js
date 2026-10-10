export const numbers = new Intl.NumberFormat('en', { maximumFractionDigits: 1 })
export const dateTime = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' })
export const shortTime = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })
export const fullDate = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })

export function availableDays(result) {
  return result ? [...new Set(result.readings.map((row) => row.timestamp.slice(0, 10)))] : []
}

export function dayReport(result, day) {
  const readings = result.readings.filter((row) => row.timestamp.startsWith(day))
  const valid = readings.filter((row) => Number.isFinite(row.litres_used))
  const scored = readings.filter((row) => Number.isFinite(row.anomaly_score))
  const alerts = readings.filter((row) => row.is_alert)
  const start = Date.parse(`${day}T00:00:00Z`)
  const end = start + 86400000
  const incidents = result.incidents.filter((row) => Date.parse(row.first_alert_at) < end && Date.parse(row.last_alert_at) >= start)
  const peak = valid.length ? valid.reduce((highest, row) => row.litres_used > highest.litres_used ? row : highest) : null
  return {
    readings, valid, scored, alerts, incidents, peak,
    total: valid.reduce((sum, row) => sum + row.litres_used, 0),
    unknown: readings.length - valid.length,
    outsideUpload: 96 - readings.length,
    positive: valid.filter((row) => row.litres_used > 0).length,
    zero: valid.filter((row) => row.litres_used === 0).length,
  }
}
