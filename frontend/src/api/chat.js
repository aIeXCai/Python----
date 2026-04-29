const BASE_URL = 'http://localhost:8080/api'

function getToken() {
  return localStorage.getItem('token')
}

/**
 * 发送聊天消息 — SSE 流式接收
 * @param {object} param
 * @param {string} param.message - 用户消息
 * @param {number|null} param.sessionId - 会话 ID（首次为 null）
 * @param {object|null} param.context - 页面上下文
 * @param {function} param.onToken - 每收到一个 token 的回调 (content: string) => void
 * @returns {Promise<{session_id: number, title: string}>}
 */
export async function sendChatMessage({ message, sessionId, context, onToken }) {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/chat/send/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Token ${token}`,
    },
    body: JSON.stringify({
      message,
      session_id: sessionId || null,
      context: context || null,
    }),
  })

  if (!response.ok) {
    let errMsg = '请求失败'
    try {
      const errData = await response.json()
      errMsg = errData.error || errMsg
    } catch {}
    if (response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    throw new Error(errMsg)
  }

  // 解析 SSE 流
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  return new Promise((resolve, reject) => {
    function pump({ done, value }) {
      if (done) {
        // 流结束但没有收到 done 事件，正常结束
        return
      }

      buffer += decoder.decode(value, { stream: true })

      // SSE 事件以 \n\n 分隔
      const parts = buffer.split('\n\n')
      buffer = parts.pop()  // 保留未完成的部分

      for (const part of parts) {
        if (!part.trim()) continue

        let eventType = ''
        let eventData = ''

        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6)
          }
        }

        if (eventType === 'token' && eventData) {
          try {
            const parsed = JSON.parse(eventData)
            if (onToken) onToken(parsed.content || '')
          } catch {}
        } else if (eventType === 'done' && eventData) {
          try {
            resolve(JSON.parse(eventData))
          } catch {
            resolve(null)
          }
          return
        } else if (eventType === 'error' && eventData) {
          try {
            const parsed = JSON.parse(eventData)
            reject(new Error(parsed.error || 'AI 服务异常'))
          } catch {
            reject(new Error('AI 服务异常'))
          }
          return
        }
      }

      reader.read().then(pump).catch(reject)
    }

    reader.read().then(pump).catch(reject)
  })
}

/**
 * 获取当前学生的会话列表
 */
export async function getChatSessions() {
  const token = getToken()
  const response = await fetch(`${BASE_URL}/chat/sessions/`, {
    headers: { Authorization: `Token ${token}` },
  })

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    throw new Error('获取会话列表失败')
  }

  const data = await response.json()
  return data.sessions || []
}

/**
 * 获取某个会话的消息记录
 */
export async function getChatMessages(sessionId) {
  const token = getToken()
  const response = await fetch(`${BASE_URL}/chat/sessions/${sessionId}/messages/`, {
    headers: { Authorization: `Token ${token}` },
  })

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    throw new Error('获取消息失败')
  }

  return response.json()
}

/**
 * 删除一个会话
 */
export async function deleteChatSession(sessionId) {
  const token = getToken()
  const response = await fetch(`${BASE_URL}/chat/sessions/${sessionId}/`, {
    method: 'DELETE',
    headers: { Authorization: `Token ${token}` },
  })

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    throw new Error('删除会话失败')
  }

  return response.json()
}
