import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ARTICLE_MODES, LANGUAGE_NAMES, typingApi, typingError } from '../../api/typing.js'
import '../typing.css'

const LANGUAGES = Object.keys(LANGUAGE_NAMES)

export default function TypingTeacher() {
  const dialog = useRef(null)
  const [classes, setClasses] = useState([])
  const [selection, setSelection] = useState('')
  const [scope, setScope] = useState(null)
  const [options, setOptions] = useState(null)
  const [mode, setMode] = useState('random')
  const [pinyin, setPinyin] = useState(false)
  const [fixed, setFixed] = useState({})
  const [editing, setEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [grade, classNum] = selection ? JSON.parse(selection) : []
  const current = scope?.selection === selection ? scope.activity : null

  useEffect(() => {
    const controller = new AbortController()
    typingApi.teacherClasses(controller.signal)
      .then(classOptions => {
        if (controller.signal.aborted) return
        setClasses(classOptions)
        const first = classOptions.find(item => item.classes.length)
        if (first) setSelection(JSON.stringify([first.grade, first.classes[0]]))
      })
      .catch(err => { if (!controller.signal.aborted) setError(typingError(err)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!grade || !classNum) return
    const controller = new AbortController()
    typingApi.teacherSettings({ grade, class_num: classNum }, controller.signal)
      .then(activity => {
        if (!controller.signal.aborted) setScope({ selection, activity })
      })
      .catch(err => { if (!controller.signal.aborted) setError(typingError(err)) })
    return () => controller.abort()
  }, [grade, classNum, selection])

  useEffect(() => {
    if (!editing) return
    const controller = new AbortController()
    Promise.all(LANGUAGES.map(language => typingApi.teacherArticles({
      grade, class_num: classNum, language, pinyin: language === 'zh' && pinyin,
    }, controller.signal)))
      .then(([zh, en]) => { if (!controller.signal.aborted) setOptions({ selection, pinyin, zh, en }) })
      .catch(err => { if (!controller.signal.aborted) setError(typingError(err)) })
    return () => controller.abort()
  }, [editing, grade, classNum, pinyin, selection])

  const available = options?.selection === selection && options.pinyin === pinyin ? options : null
  const ready = LANGUAGES.every(language => available?.[language].length)
  const articlesByLanguage = ready ? Object.fromEntries(LANGUAGES.map(language => [
    language, available[language].flatMap(({ difficulty, articles }) =>
      articles.map(article => ({ ...article, difficulty }))),
  ])) : {}
  const selectedArticle = language => {
    const articles = articlesByLanguage[language]
    return articles?.find(article => article.id === fixed[language])
  }
  const canSave = ready && (mode !== 'fixed' || LANGUAGES.every(language => selectedArticle(language)))

  function open() {
    setError('')
    setNotice('')
    setOptions(null)
    setMode(current?.languages.zh.mode || 'random')
    setPinyin(current?.languages.zh.pinyin || false)
    setFixed(Object.fromEntries(LANGUAGES.map(language => [language, current?.languages[language].article_id])))
    setEditing(true)
    dialog.current.showModal()
  }

  async function save(event) {
    event.preventDefault()
    if (!canSave || pending) return
    setPending(true)
    setError('')
    const payload = { grade, class_num: classNum }
    for (const language of LANGUAGES) {
      const previous = current?.languages[language]
      const pool = available[language]
      const difficulty = pool.find(option => option.difficulty === previous?.difficulty)?.difficulty || pool[0].difficulty
      const article = mode === 'fixed' ? selectedArticle(language) : null
      payload[language] = {
        mode,
        difficulty: article?.difficulty || difficulty,
        pinyin: language === 'zh' && pinyin,
        ...(article ? { article_id: article.id } : {}),
      }
    }
    try {
      const activity = await typingApi.publish(payload)
      setScope({ selection, activity })
      setNotice('设置已保存，下次开始练习时生效。')
      dialog.current.close()
    } catch (err) {
      setError(typingError(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="typing-page">
      <Link to="/teacher/dashboard">‹ 返回教师后台</Link>
      <h1>打字训练</h1>
      {loading && <p role="status">正在加载班级…</p>}
      {error && !editing && <p role="alert" className="typing-error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!loading && !selection && !error && <p>当前管理范围内没有可用班级。</p>}
      {selection && <section className="typing-panel">
        <div className="typing-settings-actions">
          <label>班级
            <select value={selection} onChange={event => {
              setSelection(event.target.value)
              setNotice('')
              setError('')
            }}>
              {classes.flatMap(item => item.classes.map(classId => (
                <option key={`${item.grade}:${classId}`} value={JSON.stringify([item.grade, classId])}>{item.label} {classId} 班</option>
              )))}
            </select>
          </label>
          <button type="button" className="typing-primary" aria-haspopup="dialog"
            disabled={scope?.selection !== selection} onClick={open}>参数设置</button>
        </div>
        {current && <div>
          <p>文章模式 · {current.languages.zh.mode === current.languages.en.mode
            ? ARTICLE_MODES[current.languages.zh.mode]
            : LANGUAGES.map(language => LANGUAGE_NAMES[language] + ' ' + ARTICLE_MODES[current.languages[language].mode]).join('／')}</p>
          <p>显示拼音 · {current.languages.zh.pinyin ? '开' : '关'}</p>
        </div>}
      </section>}

      <dialog ref={dialog} className="typing-settings-dialog" aria-labelledby="typing-settings-title"
        onClose={() => setEditing(false)} onCancel={event => { if (pending) event.preventDefault() }}>
        {editing && <form onSubmit={save}>
          <h2 id="typing-settings-title">参数设置</h2>
          <label>文章模式
            <select value={mode} onChange={event => setMode(event.target.value)} autoFocus>
              {['random', 'fixed', 'free'].map(value => <option key={value} value={value}>{ARTICLE_MODES[value]}</option>)}
            </select>
          </label>
          {mode === 'fixed' && ready && LANGUAGES.map(language => <label key={language}>{LANGUAGE_NAMES[language]}固定文章
            <select value={selectedArticle(language)?.id ?? ''} onChange={event => setFixed(previous => ({
              ...previous, [language]: Number(event.target.value),
            }))}>
              <option value="">请选择文章</option>
              {articlesByLanguage[language].map(article => <option key={article.id} value={article.id}>{article.title}</option>)}
            </select>
          </label>)}
          <label className="typing-checkbox">
            <input type="checkbox" checked={pinyin} onChange={event => {
              setError('')
              setPinyin(event.target.checked)
            }} />
            显示拼音
          </label>
          {!available && !error && <p role="status">正在读取题库…</p>}
          {available && !ready && <p role="status">当前设置缺少可用文章。</p>}
          {error && <p role="alert" className="typing-error">{error}</p>}
          <div className="typing-dialog-actions">
            <button type="button" disabled={pending} onClick={() => dialog.current.close()}>取消</button>
            <button type="submit" className="typing-primary" disabled={!canSave || pending}>保存设置</button>
          </div>
        </form>}
      </dialog>
    </main>
  )
}
