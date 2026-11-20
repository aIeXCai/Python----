import { Fragment, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ARTICLE_MODES, LANGUAGE_NAMES, typingApi, typingError } from '../../api/typing.js'
import '../typing.css'

function Peak({ peak }) {
  return (
    <figure className="typing-peak">
      <img src={`${import.meta.env.BASE_URL}typing-peaks/${peak.id}.webp`} alt="" />
      <figcaption><strong>{peak.name}</strong><span>{peak.route}</span></figcaption>
    </figure>
  )
}

function Article({ article }) {
  const [position, setPosition] = useState(null)
  let offset = 0

  return (
    <article className="typing-panel typing-article">
      <h2>{article.title}</h2>
      {article.pinyin && (
        <p aria-live="polite">{position === null ? '点一个汉字查看拼音。' : article.pinyin[position]}</p>
      )}
      {article.paragraphs.map((paragraph, index) => {
        const start = offset
        const characters = [...paragraph]
        offset += characters.length
        return <p key={index}>{article.pinyin ? characters.map((char, localIndex) => {
          const i = start + localIndex
          return article.pinyin[i]
            ? <button type="button" key={i} className="typing-character" aria-pressed={position === i}
                onClick={() => setPosition(i)}>{char}</button>
            : <Fragment key={i}>{char}</Fragment>
        }) : paragraph}</p>
      })}
    </article>
  )
}

function StartedAttempt({ attempt, onLeave }) {
  const [milliseconds, setMilliseconds] = useState(null)
  const peak = attempt.activity.languages[attempt.language].peak

  useEffect(() => {
    const remaining = Date.parse(attempt.deadline_at) - Date.parse(attempt.server_now)
    const until = performance.now() + remaining
    const update = () => setMilliseconds(Math.max(0, until - performance.now()))
    update()
    const timer = window.setInterval(update, 200)
    return () => window.clearInterval(timer)
  }, [attempt])

  const seconds = Math.ceil(milliseconds / 1000)
  return (
    <>
      <section className="typing-panel">
        <div className="typing-activity">
          <h2>{attempt.activity.title} · {LANGUAGE_NAMES[attempt.language]}</h2>
          <output className="typing-timer" aria-label="剩余时间">
            {milliseconds === null ? '—' : `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`}
          </output>
        </div>
        <Peak peak={peak} />
        {milliseconds === 0 && <p role="status">本次五分钟训练已结束。</p>}
        <button type="button" onClick={onLeave}>{milliseconds === 0 ? '返回训练列表' : '返回列表（训练继续计时）'}</button>
      </section>
      {milliseconds !== 0 && <Article key={attempt.id} article={attempt.article} />}
    </>
  )
}

export default function TypingStudent() {
  const [params, setParams] = useSearchParams()
  const attemptId = params.get('attempt')
  const [activities, setActivities] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [reloadCount, setReloadCount] = useState(0)
  const [language, setLanguage] = useState('zh')
  const [articleId, setArticleId] = useState('')
  const [attempt, setAttempt] = useState(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (attempt && String(attempt.id) === attemptId) return
    const controller = new AbortController()
    const load = async () => {
      setError('')
      setLoading(true)
      if (attemptId) {
        const response = await typingApi.attempt(attemptId, controller.signal)
        if (!controller.signal.aborted) setAttempt(response)
      } else {
        const response = await typingApi.activities(controller.signal)
        if (!controller.signal.aborted) {
          setActivities(response.activities)
          setActiveId(response.active_attempt_id)

        }
      }
    }
    load().catch(err => {
      if (!controller.signal.aborted) setError(typingError(err))
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [attemptId, attempt, reloadCount])

  const activity = activities[0]
  const setup = activity?.languages[language]
  const article = setup?.articles?.find(item => String(item.id) === articleId) || setup?.articles?.[0]

  async function start() {
    if (!activity || starting) return
    setStarting(true)
    setError('')
    try {
      const response = await typingApi.start({
        activity_id: activity.id, language,
        ...(setup.mode === 'free' ? { article_id: article?.id } : {}),
      })
      setAttempt(response)
      setParams({ attempt: response.id })
    } catch (err) {
      setError(typingError(err))
    } finally {
      setStarting(false)
    }
  }

  function leave() {
    setAttempt(null)
    setParams({})
  }

  const showingAttempt = attemptId && String(attempt?.id) === attemptId
  return (
    <main className="typing-page">
      <Link to="/course-select">‹ 返回欢迎页</Link>
      <h1>打字训练</h1>
      {loading && !showingAttempt && <p role="status">正在加载…</p>}
      {error && <p role="alert" className="typing-error">{error}</p>}
      {error && !attemptId && <button type="button" onClick={() => setReloadCount(count => count + 1)}>刷新训练设置</button>}
      {attemptId && error && <button type="button" onClick={leave}>返回训练列表</button>}
      {showingAttempt && <StartedAttempt attempt={attempt} onLeave={leave} />}
      {!attemptId && !loading && <>
        {activeId && <section className="typing-panel">
          <p>你有一场正在计时的训练。</p>
          <button className="typing-primary" type="button" onClick={() => setParams({ attempt: activeId })}>继续训练</button>
        </section>}
        {!activity && !error && <p>本年级暂无可用练习文章，请联系老师。</p>}
        {activity && <section className="typing-panel">
          <div className="typing-grid">
            <label>练习语言<select value={language} onChange={event => {
              setLanguage(event.target.value)
              setArticleId('')
            }}>
              {Object.entries(LANGUAGE_NAMES).map(([value, name]) => <option key={value} value={value}>{name}</option>)}
            </select></label>
          </div>
          <Peak peak={setup.peak} />
          <p>{ARTICLE_MODES[setup.mode]} · {setup.difficulty}{language === 'zh' && (setup.pinyin ? ' · 可查看拼音' : ' · 拼音关闭')}</p>
          {setup.mode === 'free' && <label>练习文章<select value={article?.id ?? ''} onChange={event => setArticleId(event.target.value)}>
            {!article && <option value="">暂无可用文章</option>}
            {setup.articles.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select></label>}
          <button className="typing-primary" type="button" onClick={start}
            disabled={Boolean(activeId || starting || (setup.mode === 'free' && !article))}>
            开始五分钟训练
          </button>
        </section>}
      </>}
    </main>
  )
}
