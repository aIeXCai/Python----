export function normalizeApiBase(rawValue) {
  const value = typeof rawValue === 'string' ? rawValue.trim() : ''
  if (!value) return '/api'

  const withoutTrailingSlashes = value.replace(/\/+$/, '')
  return withoutTrailingSlashes || '/api'
}

export const API_BASE_URL = normalizeApiBase(import.meta.env?.VITE_API_BASE_URL)

export function apiUrl(path = '') {
  const normalizedPath = String(path).replace(/^\/+/, '')
  return normalizedPath ? `${API_BASE_URL}/${normalizedPath}` : API_BASE_URL
}
