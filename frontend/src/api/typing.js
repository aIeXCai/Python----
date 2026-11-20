import { request } from './index.js'

export const typingApi = {
  teacherClasses: signal => request('/typing/teacher/classes/', { signal }),
  teacherArticles: (query, signal) => request('/typing/teacher/articles/?' + new URLSearchParams(query), { signal }),
  teacherActivities: signal => request('/typing/teacher/activities/', { signal }),
  publish: payload => request('/typing/teacher/activities/', { method: 'POST', body: JSON.stringify(payload) }),
  close: id => request(`/typing/teacher/activities/${id}/close/`, { method: 'POST' }),
  activities: signal => request('/typing/activities/', { signal }),
  attempt: (id, signal) => request(`/typing/attempts/${id}/`, { signal }),
  start: payload => request('/typing/attempts/', { method: 'POST', body: JSON.stringify(payload) }),
}

export const LANGUAGE_NAMES = { zh: '中文', en: '英文' }
export const ARTICLE_MODES = { fixed: '固定文章', random: '随机文章', free: '学生自选文章' }

export function typingError(error) {
  const detail = error.data?.detail
  if (typeof detail === 'string') return detail
  const details = Object.values(error.data || {}).flatMap(value => (
    typeof value === 'object' && value !== null ? Object.values(value).flat() : [value]
  )).filter(value => typeof value === 'string')
  return details.join('。') || error.message
}
