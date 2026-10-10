import { useEffect, useState } from 'react'
import { apiRequest } from './api'
import { dateTime } from './analysis'
import { navigate } from './navigation'

const emailLabels = { disabled: 'Email off for this upload', pending: 'Email queued', sending: 'Email sending / awaiting result', accepted: 'Accepted by email service', failed: 'Email needs attention' }

export default function Notifications({ inbox }) {
  const [settings, setSettings] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    apiRequest('/notification-settings', { signal: controller.signal }).then(setSettings).catch((failure) => { if (!controller.signal.aborted) setError(failure.message) })
    return () => controller.abort()
  }, [])

  async function action(key, run) {
    setBusy(key); setError('')
    try { await run(); await inbox.refresh() }
    catch (failure) { setError(failure.message) }
    finally { setBusy('') }
  }
  return <>
    <div className="page-heading"><p className="eyebrow">STAY INFORMED</p><h1>A heads-up, when it matters.</h1><p>New suspected episodes are grouped into one notification for each upload.</p></div>
    <div className="notification-settings">
      <section className="panel"><span className="feature-icon" aria-hidden="true">◉</span><h2>Browser notifications</h2><p>Get a desktop alert for new analysis results while LeakLens is open in this browser.</p><span className="status-badge">{inbox.browserEnabled && inbox.permission === 'granted' ? 'Enabled on this browser' : inbox.permission === 'denied' ? 'Blocked in browser settings' : inbox.permission === 'unsupported' ? 'Not supported here' : 'Not enabled'}</span><button className="secondary-button" disabled={['denied', 'unsupported'].includes(inbox.permission)} onClick={inbox.toggleBrowser}>{inbox.browserEnabled && inbox.permission === 'granted' ? 'Turn off browser alerts' : 'Enable browser alerts'}</button><p className="file-hint">Keep a tab open. These are upload notifications; there is no live meter connection. Your browser and operating system may also control delivery.</p></section>
      <section className="panel"><span className="feature-icon" aria-hidden="true">✉</span><h2>Email notifications</h2><p>Send a summary to the recipient configured for this installation.</p>{settings ? <><span className="status-badge">{settings.email_configured ? settings.email_enabled ? 'Email enabled' : 'Configured · email off' : 'Setup needed'}</span>{settings.email_recipient && <p className="recipient">Recipient: {settings.email_recipient}</p>}<button className="secondary-button" disabled={!settings.email_configured || Boolean(busy)} onClick={() => action('settings', async () => setSettings(await apiRequest('/notification-settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email_enabled: !settings.email_enabled, revision: settings.revision }) })))}>{busy === 'settings' ? 'Saving…' : settings.email_enabled ? 'Turn off email alerts' : 'Enable email alerts'}</button><p className="file-hint">{settings.email_configured ? 'Only new notifications are emailed after you enable this. Accepted means the email service accepted the message; inbox delivery is not confirmed.' : 'Configure an AWS SES sender, recipient, and region on the server first. Setup instructions are in deploy/AWS_STEPS.md.'}</p></> : <p>Loading email settings…</p>}</section>
    </div>
    {(error || inbox.error) && <p className="error-message" role="alert">{error || inbox.error}</p>}
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">YOUR INBOX · ALL HOUSEHOLDS</p><h2>Recent notifications <span className="count-badge">{inbox.unread_count} unread</span></h2><p>Repeated uploads of the same detected episodes do not create fresh notifications.</p></div><button className="secondary-button" onClick={inbox.refresh}>Refresh inbox</button></div>
      {inbox.notifications.length ? <div className="inbox-list">{inbox.notifications.map((event) => <article className={`inbox-item ${event.read ? '' : 'unread'}`} key={event.notification_id}><div className="inbox-heading"><h3>{event.title}</h3><time>{dateTime.format(new Date(event.created_at))} UTC</time></div><p>{event.message}</p><p className="file-hint">Reading dates: {dateTime.format(new Date(event.first_alert_at))} – {dateTime.format(new Date(event.last_alert_at))} UTC</p><span className={`status-badge email-${event.email_status}`}>{emailLabels[event.email_status] || event.email_status}</span>{event.email_error && <p className="inline-error">{event.email_error}</p>}<div className="inbox-actions"><button className="small-button" onClick={() => navigate('alerts', { analysis: event.analysis_id })}>Review analysis →</button>{!event.read && <button className="text-button" disabled={Boolean(busy)} onClick={() => action(event.notification_id, () => apiRequest(`/notifications/${event.notification_id}/read`, { method: 'POST' }))}>Mark as read</button>}{event.email_status === 'failed' && <button className="text-button" disabled={Boolean(busy) || !settings?.email_enabled} onClick={() => action(event.notification_id, () => apiRequest(`/notifications/${event.notification_id}/retry-email`, { method: 'POST' }))}>Retry email</button>}</div></article>)}</div> : <div className="empty-alerts"><h3>You’re all caught up.</h3><p>Analyse a CSV to receive notifications when new suspected episodes are found.</p></div>}
    </section>
  </>
}
