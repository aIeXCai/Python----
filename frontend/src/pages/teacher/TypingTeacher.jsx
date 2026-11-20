import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ARTICLE_MODES, LANGUAGE_NAMES, typingApi, typingError } from '../../api/typing.js'
import '../typing.css'

const EMPTY_SETUP = { mode: 'fixed', difficulty: '', articleId: '', pinyin: false }
const LANGUAGES = Object.keys(LANGUAGE_NAMES)

function LanguageFields({ language, setup, options, onChange, loading, hasClass }) {
  const key = options.find(item => item.difficulty === setup.difficulty) || options[0]
  const currentArticle = key?.articles.find(article => String(article.id) === setup.articleId) || key?.articles[0]

  return (
    <fieldset className="typing-form-panel">
      <legend>{LANGUAGE_NAMES[language]}训练</legend>
      <label>选文方式
        <select value={setup.mode} onChange={event => onChange({ mode: event.target.value })}>
          {Object.entries(ARTICLE_MODES).map(([value, name]) => <option key={value} value={value}>{name}</option>)}
        </select>
      </label>
      {language === 'zh' && <label className="typing-checkbox">
        <input type="checkbox" checked={setup.pinyin} onChange={event => onChange({
          pinyin: event.target.checked, difficulty: '', articleId: '',
        })} />
        允许学生点字查看拼音
      </label>}
      <label>难度
        <select disabled={!key || loading} value={key?.difficulty ?? ''} onChange={event => onChange({
          difficulty: event.target.value, articleId: '',
        })}>
          {!key && <option value="">暂无可用题池</option>}
          {options.map(item => <option key={item.difficulty}>{item.difficulty}</option>)}
        </select>
      </label>
      {setup.mode === 'fixed' && <label>固定文章
        <select disabled={!currentArticle || loading} value={currentArticle?.id ?? ''} onChange={event => onChange({
          articleId: event.target.value,
        })}>
          {!currentArticle && <option value="">暂无可用文章</option>}
          {key?.articles.map(article => <option key={article.id} value={article.id}>{article.title}</option>)}
        </select>
      </label>}
      {!loading && hasClass && !key && <p>请先补充可发布的{LANGUAGE_NAMES[language]}文章{setup.pinyin && '和对应拼音'}。</p>}
      {setup.mode !== 'fixed' && key && <p>可用文章 {key.articles.length} 篇</p>}
    </fieldset>
  )
}

export default function TypingTeacher() {
  const [classes, setClasses] = useState([])
  const [activities, setActivities] = useState([])
  const [title, setTitle] = useState('')
  const [selection, setSelection] = useState('')
  const [setups, setSetups] = useState({ zh: EMPTY_SETUP, en: EMPTY_SETUP })
  const [options, setOptions] = useState(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [grade, classNum] = selection ? JSON.parse(selection) : []
  const pinyin = setups.zh.pinyin

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([typingApi.teacherClasses(controller.signal), typingApi.teacherActivities(controller.signal)])
      .then(([classOptions, existing]) => {
        setClasses(classOptions)
        setActivities(existing)
        const first = classOptions.find(item => item.classes.length)
        if (first) setSelection(JSON.stringify([first.grade, first.classes[0]]))
      })
      .catch(err => { if (!controller.signal.aborted) setError(typingError(err)) })
      .finally(() => { if (!controller.signal.aborted) setInitialLoading(false) })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!grade || !classNum) return
    const controller = new AbortController()
    Promise.all(LANGUAGES.map(language => typingApi.teacherArticles({
      grade, class_num: classNum, language, pinyin: language === 'zh' && pinyin,
    }, controller.signal)))
      .then(([zh, en]) => { if (!controller.signal.aborted) setOptions({ selection, pinyin, zh, en }) })
      .catch(err => { if (!controller.signal.aborted) setError(typingError(err)) })
    return () => controller.abort()
  }, [classNum, grade, pinyin, selection])

  const currentOptions = options?.selection === selection && options.pinyin === pinyin ? options : null
  const publishable = LANGUAGES.every(language => currentOptions?.[language].length)

  async function publish(event) {
    event.preventDefault()
    if (!publishable || pending) return
    setPending(true)
    setError('')
    setNotice('')
    const payload = { title: title.trim(), grade: Number(grade), class_num: classNum }
    for (const language of LANGUAGES) {
      const setup = setups[language]
      const items = currentOptions[language]
      const chosen = items.find(item => item.difficulty === setup.difficulty) || items[0]
      payload[language] = { mode: setup.mode, difficulty: chosen.difficulty, pinyin: setup.pinyin }
      if (setup.mode === 'fixed') {
        payload[language].article_id = chosen.articles.find(article => String(article.id) === setup.articleId)?.id
          ?? chosen.articles[0].id
      }
    }
    try {
      const activity = await typingApi.publish(payload)
      setActivities(previous => [activity, ...previous])
      setTitle('')
      setNotice(`已发布「${activity.title}」。`)
    } catch (err) {
      setError(typingError(err))
    } finally {
      setPending(false)
    }
  }

  async function close(activity) {
    setPending(true)
    setError('')
    setNotice('')
    try {
      const updated = await typingApi.close(activity.id)
      setActivities(previous => previous.map(item => item.id === updated.id ? updated : item))
      setNotice(`「${activity.title}」已停止接受新练习。`)
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
      {initialLoading && <p role="status">正在加载班级…</p>}
      {error && <p role="alert" className="typing-error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!initialLoading && !classes.some(item => item.classes.length) && <p>当前管理范围内没有可用班级。</p>}
      {!!classes.length && <form className="typing-panel" onSubmit={publish}>
        <h2>发布新训练</h2>
        <div className="typing-grid">
          <label>训练名称<input required maxLength={100} value={title} onChange={event => setTitle(event.target.value)} /></label>
          <label>班级<select disabled={!selection} value={selection} onChange={event => {
            setSelection(event.target.value)
            setSetups({ zh: EMPTY_SETUP, en: EMPTY_SETUP })
            setError('')
          }}>
            {!selection && <option value="">暂无班级</option>}
            {classes.flatMap(item => item.classes.map(classId => (
              <option key={`${item.grade}:${classId}`} value={JSON.stringify([item.grade, classId])}>{item.label} {classId} 班</option>
            )))}
          </select></label>
        </div>
        <div className="typing-grid">
          {LANGUAGES.map(language => <LanguageFields
            key={language} language={language} setup={setups[language]} options={currentOptions?.[language] || []}
            loading={Boolean(selection && !currentOptions && !error)} hasClass={Boolean(selection)}
            onChange={change => setSetups(previous => ({ ...previous, [language]: { ...previous[language], ...change } }))}
          />)}
        </div>
        <button className="typing-primary" disabled={pending || !publishable || !title.trim()}>发布训练</button>
      </form>}
      <section className="typing-panel">
        <h2>已发布训练</h2>
        {!activities.length && <p>暂无训练。</p>}
        {activities.map(activity => <article className="typing-activity" key={activity.id}>
          <div>
            <h3>{activity.title}</h3>
            <p>{activity.grade} 年级 {activity.class_num} 班 · {activity.closed_at ? '已停止加入' : '接受加入'}</p>
            {LANGUAGES.map(language => {
              const setup = activity.languages[language]
              return <p key={language}>{LANGUAGE_NAMES[language]} · {setup.peak.name} · {ARTICLE_MODES[setup.mode]}{setup.pinyin && ' · 拼音开启'}</p>
            })}
          </div>
          {!activity.closed_at && <button type="button" disabled={pending} onClick={() => close(activity)}>停止加入</button>}
        </article>)}
      </section>
    </main>
  )
}
