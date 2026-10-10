import { useState } from 'react'
import { downloadAnalysisCsv, downloadTicketCsv, printAnalysis, printTicket } from './reports'

export default function ReportActions({ result, day, ticket }) {
  const [error, setError] = useState('')
  function print() {
    setError('')
    try { if (ticket) printTicket(ticket); else printAnalysis(result, day) } catch (failure) { setError(failure.message) }
  }
  return <div className="report-actions"><button className="secondary-button" onClick={() => ticket ? downloadTicketCsv(ticket) : downloadAnalysisCsv(result, day)}>↓ Download CSV</button><button className="secondary-button" onClick={print}>Print / save PDF ↗</button>{error && <p className="inline-error" role="alert">{error}</p>}</div>
}
