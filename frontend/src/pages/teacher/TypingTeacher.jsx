import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ARTICLE_MODES, LANGUAGE_NAMES, typingApi, typingError } from '../../api/typing.js'
import '../typing.css'

const EMPTY_SETUP = { mode: 'random', difficulty: '', articleId: '', pinyin: false }
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
  const [loadedScope, setLoadedScope] = useState(null)
  const [current, setCurrent] = useState(null)
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
    typingApi.teacherClasses(controller.signal)
      .then(classOptions => {
        setClasses(classOptions)
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
    typingApi.teacherSettings({ grade, class_num: classNum }, controller.signal)
      .then(activity => {
        if (controller.signal.aborted) return
        setCurrent(activity)
        setSetups(Object.fromEntries(LANGUAGES.map(language => {
          const saved = activity?.languages[language]
          return [language, saved ? {
            mode: saved.mode, difficulty: saved.difficulty,
            articleId: saved.article_id ? String(saved.article_id) : '', pinyin: saved.pinyin,
          } : EMPTY_SETUP]
        })))
        setLoadedScope(selection)
      })
      .catch(err => { if (!controller.signal.aborted) setError(typingError(err)) })
    return () => controller.abort()
  }, [classNum, grade, selection])

  useEffect(() => {
    if (!grade || !classNum || loadedScope !== selection) return
    const controller = new AbortController()
    Promise.all(LANGUAGES.map(language => typingApi.teacherArticles({
      grade, class_num: classNum, language, pinyin: language === 'zh' && pinyin,
    }, controller.signal)))
      .then(([zh, en]) => { if (!controller.signal.aborted) setOptions({ selection, pinyin, zh, en }) })
      .catch(err => { if (!controller.signal.aborted) setError(typingError(err)) })
    return () => controller.abort()
  }, [classNum, grade, loadedScope, pinyin, selection])

  const currentOptions = loadedScope === selection && options?.selection === selection && options.pinyin === pinyin ? options : null
  const publishable = LANGUAGES.every(language => currentOptions?.[language].length)

  async function publish(event) {
    event.preventDefault()
    if (!publishable || pending) return
    setPending(true)
    setError('')
    setNotice('')
    const payload = { grade: Number(grade), class_num: classNum }
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
      setCurrent(activity)
      setNotice('设置已保存，下次开始练习时生效。')
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
        <h2>班级训练设置</h2>
        <label>班级<select disabled={!selection || pending} value={selection} onChange={event => {
            setSelection(event.target.value)
            setLoadedScope(null)
            setCurrent(null)
            setNotice('')
            setError('')
          }}>
            {!selection && <option value="">暂无班级</option>}
            {classes.flatMap(item => item.classes.map(classId => (
              <option key={`${item.grade}:${classId}`} value={JSON.stringify([item.grade, classId])}>{item.label} {classId} 班</option>
            )))}
          </select></label>
        {selection && loadedScope !== selection && !error && <p role="status">正在读取设置…</p>}
        {loadedScope === selection && <div className="typing-grid">
          {LANGUAGES.map(language => <LanguageFields
            key={language} language={language} setup={setups[language]} options={currentOptions?.[language] || []}
            loading={Boolean(selection && !currentOptions && !error)} hasClass={Boolean(selection)}
            onChange={change => setSetups(previous => ({ ...previous, [language]: { ...previous[language], ...change } }))}
          />)}
        </div>}
        <button className="typing-primary" disabled={pending || !publishable}>保存设置</button>
      </form>}
      {current && loadedScope === selection && <section className="typing-panel">
        <h2>{current.is_default ? '当前使用默认设置' : '当前生效设置'}</h2>
        {LANGUAGES.map(language => {
          const setup = current.languages[language]
          return <p key={language}>{LANGUAGE_NAMES[language]} · {setup.peak.name} · {ARTICLE_MODES[setup.mode]} · {setup.difficulty}{setup.pinyin && ' · 拼音开启'}</p>
        })}
      </section>}
    </main>
  )
}
