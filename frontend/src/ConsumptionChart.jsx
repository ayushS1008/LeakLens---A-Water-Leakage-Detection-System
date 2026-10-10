import { useEffect, useRef, useState } from 'react'
import { dateTime, numbers, shortTime } from './analysis'

export default function ConsumptionChart({ readings, day }) {
  const [selection, setSelection] = useState(null)
  const [size, setSize] = useState({ width: 1000, height: 300 })
  const svg = useRef(null)
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width > 0 && height > 0) setSize({ width, height })
    })
    observer.observe(svg.current)
    return () => observer.disconnect()
  }, [])
  const { width, height } = size
  const left = width < 520 ? 42 : 52
  const right = width < 520 ? 12 : 20
  const top = 30
  const bottom = 42
  const midnight = Date.parse(`${day}T00:00:00Z`)
  const maximum = Math.max(5, ...readings.map((row) => row.litres_used ?? 0))
  const ceiling = Math.ceil(maximum / 5) * 5
  const x = (row) => left + ((Date.parse(row.timestamp) - midnight) / 86400000) * (width - left - right)
  const y = (value) => height - bottom - (value / ceiling) * (height - top - bottom)
  const segments = []
  let points = []
  for (const row of readings) {
    if (Number.isFinite(row.litres_used)) {
      points.push(`${x(row)},${y(row.litres_used)}`)
    } else if (points.length) {
      segments.push(points.join(' '))
      points = []
    }
  }
  if (points.length) segments.push(points.join(' '))
  const selectedIndex = selection?.day === day ? selection.index : -1
  const selected = readings[selectedIndex]

  function inspect(event) {
    if (!readings.length) return
    const bounds = event.currentTarget.getBoundingClientRect()
    const position = ((event.clientX - bounds.left) / bounds.width) * width
    const instant = midnight + Math.max(0, Math.min(1, (position - left) / (width - left - right))) * 86400000
    let nearest = 0
    for (let index = 1; index < readings.length; index++) {
      if (Math.abs(Date.parse(readings[index].timestamp) - instant) < Math.abs(Date.parse(readings[nearest].timestamp) - instant)) nearest = index
    }
    setSelection({ day, index: nearest })
  }

  function keyboard(event) {
    if (event.key === 'Escape') { setSelection(null); return }
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || !readings.length) return
    event.preventDefault()
    let index = Math.max(0, selectedIndex)
    if (event.key === 'ArrowLeft') index = Math.max(0, index - 1)
    if (event.key === 'ArrowRight') index = Math.min(readings.length - 1, index + 1)
    if (event.key === 'Home') index = 0
    if (event.key === 'End') index = readings.length - 1
    setSelection({ day, index })
  }

  return (
    <div className="chart-interaction">
      <div className="chart-canvas">
        <svg ref={svg} className="consumption-chart" viewBox={`0 0 ${width} ${height}`} role="img" tabIndex={0} aria-describedby={selected ? 'chart-reading-details' : undefined}
          aria-label={`Water use on ${day}, UTC. Move the pointer or use the arrow keys to inspect readings. Orange points mark alerts; gaps are unknown.`}
          onPointerMove={inspect} onPointerDown={inspect} onPointerLeave={(event) => { if (event.pointerType !== 'touch') setSelection(null) }}
          onKeyDown={keyboard} onBlur={() => setSelection(null)}>
          {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
            <g key={fraction}>
              <line x1={left} x2={width - right} y1={y(ceiling * fraction)} y2={y(ceiling * fraction)} className="grid-line" />
              <text x={left - 10} y={y(ceiling * fraction) + 4} textAnchor="end">{numbers.format(ceiling * fraction)}</text>
            </g>
          ))}
          {(width < 600 ? [0, 6, 12, 18, 24] : [0, 4, 8, 12, 16, 20, 24]).map((hour) => (
            <text key={hour} x={left + (hour / 24) * (width - left - right)} y={height - 12} textAnchor="middle">{String(hour).padStart(2, '0')}:00</text>
          ))}
          {segments.map((segment, index) => <polyline key={index} points={segment} fill="none" stroke="#14867e" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />)}
          {readings.filter((row) => Number.isFinite(row.litres_used)).map((row) => (
            <circle key={row.timestamp} cx={x(row)} cy={y(row.litres_used)} r={row.is_alert ? 4.5 : 2.2} fill={row.is_alert ? '#d67a3c' : '#14867e'} />
          ))}
          {selected && <g className="chart-selection">
            <line x1={x(selected)} x2={x(selected)} y1={top} y2={height - bottom} stroke="#8caaa0" strokeDasharray="4 5" />
            {Number.isFinite(selected.litres_used) && <circle cx={x(selected)} cy={y(selected.litres_used)} r="6" stroke="#fff" strokeWidth="2" fill={selected.is_alert ? '#d67a3c' : '#14867e'} />}
          </g>}
        </svg>
        {selected && <div id="chart-reading-details" role="tooltip" className="chart-tooltip" style={{ left: `clamp(110px, ${x(selected) / width * 100}%, calc(100% - 110px))` }}>
          <span>{dateTime.format(new Date(selected.timestamp))} UTC</span>
          <strong>{Number.isFinite(selected.litres_used) ? `${numbers.format(selected.litres_used)} L` : 'Unknown reading'}</strong>
          <p>{shortTime.format(new Date(Date.parse(selected.timestamp) - 900000))}–{shortTime.format(new Date(selected.timestamp))} · 15-minute interval</p>
          <span className={selected.is_alert ? 'tooltip-alert' : ''}>{selected.is_alert ? 'Suspected leak alert' : Number.isFinite(selected.anomaly_score) ? 'No alert at this interval' : 'Not scored · incomplete context'}</span>
          {Number.isFinite(selected.anomaly_score) && <small>Anomaly score {selected.anomaly_score.toFixed(3)} · not a probability</small>}
        </div>}
      </div>
      <p className="chart-help"><span aria-hidden="true">↔</span> Move over the chart for instant details. Tap on mobile, or focus the chart and use ← →.</p>
    </div>
  )
}
