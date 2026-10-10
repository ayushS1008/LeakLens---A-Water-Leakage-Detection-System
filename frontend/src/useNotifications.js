import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from './api'

function saved(key) { try { return localStorage.getItem(key) } catch { return null } }
function save(key, value) { try { localStorage.setItem(key, value) } catch { /* Notifications still work for this tab. */ } }

export default function useNotifications() {
  const [inbox, setInbox] = useState({ notifications: [], unread_count: 0 })
  const [error, setError] = useState('')
  const [browserEnabled, setBrowserEnabled] = useState(() => saved('leaklens-browser-enabled') === 'true')
  const [permission, setPermission] = useState(() => 'Notification' in window ? Notification.permission : 'unsupported')
  const refresh = useCallback(async () => {
    try { setInbox(await apiRequest('/notifications')); setError('') }
    catch (failure) { setError(failure.message) }
  }, [])

  useEffect(() => {
    let active = true
    async function poll() {
      try { const body = await apiRequest('/notifications'); if (active) { setInbox(body); setError('') } }
      catch (failure) { if (active) setError(failure.message) }
    }
    poll()
    const timer = setInterval(poll, 30000)
    return () => { active = false; clearInterval(timer) }
  }, [])

  useEffect(() => {
    if (!browserEnabled || permission !== 'granted') return
    const since = Number(saved('leaklens-browser-since') || Date.now())
    for (const event of inbox.notifications) {
      const key = `leaklens-notified-${event.notification_id}`
      if (event.read || Date.parse(event.created_at) < since || saved(key)) continue
      try {
        const notification = new Notification(event.title, { body: 'New patterns in uploaded readings. Open LeakLens to review.', tag: event.notification_id })
        notification.onclick = () => { window.focus(); window.location.hash = `/alerts?analysis=${encodeURIComponent(event.analysis_id)}`; notification.close() }
        save(key, 'true')
      } catch { /* Some browsers permit permission but do not support desktop notifications. */ }
    }
  }, [inbox, browserEnabled, permission])

  async function toggleBrowser() {
    if (browserEnabled && permission === 'granted') { save('leaklens-browser-enabled', 'false'); setBrowserEnabled(false); return }
    if (!('Notification' in window)) return
    try {
      const choice = await Notification.requestPermission()
      setPermission(choice)
      if (choice === 'granted') {
        save('leaklens-browser-since', String(Date.now())); save('leaklens-browser-enabled', 'true'); setBrowserEnabled(true)
      }
    } catch { setError('This browser could not enable notifications. Try a supported browser on localhost or HTTPS.') }
  }
  return { ...inbox, error, refresh, browserEnabled, permission, toggleBrowser }
}
