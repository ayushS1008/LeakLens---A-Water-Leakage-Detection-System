export function readRoute() {
  const [path, query = ''] = window.location.hash.slice(1).split('?')
  const page = (path || '/').replace(/^\//, '') || 'overview'
  const params = new URLSearchParams(query)
  return {
    page: ['overview', 'alerts', 'maintenance', 'day', 'households', 'notifications'].includes(page) ? page : 'overview',
    analysis: params.get('analysis') || '',
    date: params.get('date') || '',
    ticket: params.get('ticket') || '',
  }
}

export function pageLink(page, values = {}) {
  const params = new URLSearchParams(Object.entries(values).filter(([, value]) => value))
  return `#/${page === 'overview' ? '' : page}${params.size ? `?${params}` : ''}`
}

export function navigate(page, values = {}) {
  window.location.hash = pageLink(page, values).slice(1)
}
