// Shared API config and helpers.
// This file keeps all fetch logic in one place so every screen can reuse it.

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8001').replace(/\/$/, '')
export const TOKEN_KEY = 'ai-recognition-token'
export const USER_KEY = 'ai-recognition-user'
console.log("Backend URL:", API_BASE);
console.log("VITE_API_URL:", import.meta.env.VITE_API_URL);
console.log("API_BASE:", API_BASE);

export { API_BASE }

export async function request(path, { token, ...options } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      'ngrok-skip-browser-warning': 'true',
      ...options.headers,
    },
  })

  const data = response.status === 204 ? null : await response.json().catch(() => null)

  if (!response.ok) {
    const detail = Array.isArray(data?.detail)
      ? data.detail.map((item) => item.msg).join(' ')
      : data?.detail

    throw new Error(detail || `Request failed (${response.status}).`)
  }

  return data
}

export function friendlyError(error) {
  if (error instanceof TypeError) return 'Could not reach the API. Check that the backend is running.'
  return error.message || 'Something went wrong. Please try again.'
}

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export function makeGroups(entries) {
  const groups = new Map()

  entries.forEach((entry) => {
    const existing = groups.get(entry.conversation_id) || []
    existing.push(entry)
    groups.set(entry.conversation_id, existing)
  })

  return [...groups.entries()]
    .map(([id, turns]) => ({
      id,
      turns: turns.sort((a, b) => new Date(a.created_at) - new Date(b.created_at)),
    }))
    .sort((a, b) => new Date(b.turns.at(-1)?.created_at) - new Date(a.turns.at(-1)?.created_at))
}
