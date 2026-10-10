export async function apiRequest(path, options = {}) {
  let response
  try { response = await fetch(`/api${path}`, options) } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Cannot reach the backend. Keep the Python server running on port 8000, then try again.', { cause: error })
  }
  let body
  try { body = await response.json() } catch {
    throw new Error('The API returned an unreadable response. Check that the backend is running on port 8000.')
  }
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join(' ') : body.detail
    const error = new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}).`)
    error.status = response.status
    throw error
  }
  return body
}
