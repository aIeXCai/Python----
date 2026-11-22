// 公网部署环境（WorkBuddy 沙箱）的边缘网关会用它自己的 Bearer 令牌覆盖
// 浏览器发出的 Authorization 头，导致应用自身的 Token 认证永远判为“未认证”。
// 这里在 fetch 出口统一额外附一份 X-Auth-Token（边缘网关不会改写自定义头），
// 由部署网关（deploy/public/server.py）在转发给 Django 前翻译回 Authorization。
// 本地开发/教室机直连后端时该头不被识别，属于无害冗余。

const nativeFetch = window.fetch.bind(window)

function withAuthMirror(input, init) {
  const source = (init && init.headers) || (input && input.headers) || null
  const headers = new Headers(source || undefined)
  const auth = headers.get('Authorization')
  if (!auth) return { init, headers: null }
  headers.set('X-Auth-Token', auth)
  return { init, headers }
}

window.fetch = function patchedFetch(input, init) {
  try {
    const { headers } = withAuthMirror(input, init)
    if (!headers) return nativeFetch(input, init)
    return nativeFetch(input, { ...(init || {}), headers })
  } catch {
    return nativeFetch(input, init)
  }
}
