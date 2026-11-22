import { request } from './index.js'

export const typingApi = {
  teacherSettings: signal => request('/typing/teacher/settings/', { signal }),
  teacherArticles: (pinyin, signal) => request('/typing/teacher/settings/articles/?' + new URLSearchParams({ pinyin }), { signal }),
  updateTeacherSettings: payload => request('/typing/teacher/settings/', { method: 'POST', body: JSON.stringify(payload) }),
  bests: signal => request('/typing/me/bests/', { signal, redirectOnUnauthorized: false }),
  todayBests: signal => request('/typing/me/bests/?period=today', { signal }),
  activities: signal => request('/typing/activities/', { signal }),
  attempt: (id, signal) => request(`/typing/attempts/${id}/`, { signal }),
  start: (payload, signal) => request('/typing/attempts/', { method: 'POST', body: JSON.stringify(payload), signal }),
  board: (activity, language, signal) => request(`/typing/activities/${activity}/leaderboard/?` + new URLSearchParams({ language }), { signal }),
  pause: (attempt, payload, signal) => request(`/typing/attempts/${attempt}/pause/`, { method: 'POST', body: JSON.stringify(payload), signal }),
  resume: (attempt, signal) => request(`/typing/attempts/${attempt}/resume/`, { method: 'POST', signal }),
  sync: (attempt, payload, signal) => request(`/typing/attempts/${attempt}/sync/`, { method: 'POST', body: JSON.stringify(payload), signal }),
}

export const LANGUAGE_NAMES = { zh: '中文', en: '英文' }
export const ARTICLE_MODES = { fixed: '固定文章', random: '随机选择', free: '自由练习' }

export function typingError(error) {
  const detail = error.data?.detail
  if (typeof detail === 'string') return detail
  const details = Object.values(error.data || {}).flatMap(value => (
    typeof value === 'object' && value !== null ? Object.values(value).flat() : [value]
  )).filter(value => typeof value === 'string')
  return details.join('。') || error.message
}
