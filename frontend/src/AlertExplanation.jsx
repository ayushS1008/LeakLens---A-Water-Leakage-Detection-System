import { numbers } from './analysis'

export default function AlertExplanation({ explanation, compact = false }) {
  if (!explanation) return <p className="file-hint">Analyse the readings again to see the evidence behind this alert.</p>
  const evidence = explanation.evidence
  return <details className={`alert-explanation ${compact ? 'compact' : ''}`}><summary>Why was this flagged? <span aria-hidden="true">↗</span></summary><div className="explanation-body"><div className="evidence-chips"><span><strong>{evidence.positive_use_minutes} min</strong>with use in every interval</span><span><strong>{numbers.format(evidence.litres_in_trigger_hour)} L</strong>in the trigger hour</span><span><strong>{evidence.consecutive_unusual_intervals} / 4</strong>unusually scored intervals</span></div><ul>{explanation.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul><p>{explanation.limitation}</p></div></details>
}
