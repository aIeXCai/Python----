import assert from 'node:assert/strict'

import { API_BASE_URL, apiUrl, normalizeApiBase } from '../src/api/config.js'


assert.equal(API_BASE_URL, '/api')
assert.equal(normalizeApiBase(), '/api')
assert.equal(normalizeApiBase('   '), '/api')
assert.equal(
  normalizeApiBase(' https://example.test/api/// '),
  'https://example.test/api',
)
assert.equal(apiUrl('/auth/login/'), '/api/auth/login/')
assert.equal(apiUrl('auth/login/'), '/api/auth/login/')
assert.equal(apiUrl(), '/api')

const calls = []
globalThis.localStorage = {
  getItem: (key) => (key === 'token' ? 'verification-token' : null),
  setItem: () => {},
  removeItem: () => {},
}
globalThis.fetch = async (url, options = {}) => {
  calls.push({ url, options })
  return {
    ok: true,
    status: 200,
    json: async () => ({ sessions: [], output: 'ok' }),
  }
}

const { runCode } = await import('../src/api/index.js')
const { getChatSessions } = await import('../src/api/chat.js')
const { getInfoQuizzes } = await import('../src/api/info.js')

await runCode('print("ok")')
await getChatSessions()
await getInfoQuizzes()

assert.deepEqual(
  calls.map(({ url }) => url),
  [
    '/api/ai/run_code/',
    '/api/chat/sessions/',
    '/api/info/quizzes/',
  ],
)

console.log('API config and three runtime API modules verification passed')
