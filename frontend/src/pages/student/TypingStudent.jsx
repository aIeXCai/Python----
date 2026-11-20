import { useLayoutEffect, useRef } from 'react'
import { typingApi, typingError } from '../../api/typing.js'

function setCurrentAttempt(id) {
  const url = new URL(window.location.href)
  if (id) url.searchParams.set('attempt', id)
  else url.searchParams.delete('attempt')
  window.history.replaceState(window.history.state, '', url)
}

export default function TypingStudent() {
  const frame = useRef(null)

  useLayoutEffect(() => {
    const controller = new AbortController()
    const signal = controller.signal

    async function handle(event) {
      if (event.origin !== window.location.origin || event.source !== frame.current?.contentWindow) return
      if (event.data?.channel !== 'typing-workspace') return

      const { id, action, data } = event.data
      const send = (value, error) => {
        if (!signal.aborted) {
          event.source.postMessage({ channel: 'typing-response', id, value, error }, event.origin)
        }
      }
      try {
        switch (action) {
          case 'load': {
            const explicit = new URLSearchParams(window.location.search).get('attempt')
            if (explicit && /^\d+$/.test(explicit)) {
              try {
                send({ attempt: await typingApi.attempt(explicit, signal) })
                break
              } catch (error) {
                if (error.status !== 404) throw error
                setCurrentAttempt(null)
              }
            }
            const state = await typingApi.activities(signal)
            if (state.active_attempt_id) {
              const attempt = await typingApi.attempt(state.active_attempt_id, signal)
              setCurrentAttempt(attempt.id)
              send({ attempt })
            } else {
              send({ activity: state.activities[0] ?? null })
            }
            break
          }
          case 'start': {
            const attempt = await typingApi.start(data, signal)
            if (!signal.aborted) setCurrentAttempt(attempt.id)
            send(attempt)
            break
          }
          case 'board':
            send(await typingApi.board(data.activity, data.language, signal))
            break
          case 'sync':
            send(await typingApi.sync(data.attempt, { seq: data.seq, segments: data.segments }, signal))
            break
          case 'pause':
            send(await typingApi.pause(data.attempt, { seq: data.seq, segments: data.segments }, signal))
            break
          case 'resume':
            send(await typingApi.resume(data.attempt, signal))
            break
          case 'clear':
            setCurrentAttempt(null)
            send(null)
            break
        }
      } catch (error) {
        send(null, typingError(error))
      }
    }

    window.addEventListener('message', handle)
    return () => {
      controller.abort()
      window.removeEventListener('message', handle)
    }
  }, [])

  return (
    <iframe
      ref={frame}
      title="打字登山"
      src={`${import.meta.env.BASE_URL}typing-workspace/index.html`}
      style={{ display: 'block', width: '100%', height: '100dvh', border: 0 }}
    />
  )
}
