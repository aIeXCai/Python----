import { useEffect, useRef, useState } from 'react'
import { ARTICLE_MODES, LANGUAGE_NAMES, typingApi, typingError } from '../../api/typing.js'
import '../typing.css'

const LANGUAGES = Object.keys(LANGUAGE_NAMES)

export default function TypingTeacher({ open, onClose }) {
  const dialog = useRef(null)
  const [config, setConfig] = useState(null)
  const [options, setOptions] = useState(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const mode = config?.mode
  const pinyin = config?.pinyin ?? false

  useEffect(() => {
    const element = dialog.current
    if (open && !element.open) element.showModal()
    if (!open && element.open) element.close()
  }, [open])

  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    typingApi.teacherSettings(controller.signal)
      .then(data => { if (!controller.signal.aborted) setConfig(data) })
      .catch(err => { if (!controller.signal.aborted) setError(typingError(err)) })
    return () => controller.abort()
  }, [open])

  useEffect(() => {
    if (!open || mode !== 'fixed') return
    const controller = new AbortController()
    typingApi.teacherArticles(pinyin, controller.signal)
      .then(grades => { if (!controller.signal.aborted) setOptions({ pinyin, grades }) })
      .catch(err => { if (!controller.signal.aborted) setError(typingError(err)) })
    return () => controller.abort()
  }, [open, mode, pinyin])

  const availableGrades = options?.pinyin === pinyin ? options.grades : null
  const validArticle = (grade, language) => {
    const stored = config?.fixed_articles?.[grade.grade]?.[language]
    return grade.articles[language].some(article => article.id === stored) ? stored : ''
  }
  const canSave = config && (mode !== 'fixed' || (availableGrades?.length
    && availableGrades.every(grade => LANGUAGES.every(language => validArticle(grade, language)))))

  function close(saved = false) {
    setConfig(null)
    setOptions(null)
    setError('')
    onClose(saved)
  }

  async function save(event) {
    event.preventDefault()
    if (!canSave || pending) return
    setPending(true)
    setError('')
    try {
      await typingApi.updateTeacherSettings({
        mode, pinyin, fixed_articles: mode === 'fixed' ? config.fixed_articles : {},
      })
      close(true)
    } catch (err) {
      setError(typingError(err))
    } finally {
      setPending(false)
    }
  }

  function selectArticle(grade, language, value) {
    setConfig(previous => ({
      ...previous, fixed_articles: {
        ...previous.fixed_articles,
        [grade]: { ...previous.fixed_articles[grade], [language]: Number(value) },
      },
    }))
  }

  return (
    <dialog ref={dialog} className="typing-page typing-settings-dialog" aria-labelledby="typing-settings-title"
      onCancel={event => { event.preventDefault(); if (!pending) close() }}>
      <form onSubmit={save}>
        <h2 id="typing-settings-title">打字训练参数设置</h2>
        <fieldset disabled={!config || pending} className="typing-settings-fields">
          <label>文章模式
            <select value={mode || 'random'} onChange={event => {
              setError('')
              setConfig(previous => ({ ...previous, mode: event.target.value }))
            }} autoFocus>
              {['random', 'fixed', 'free'].map(value => <option key={value} value={value}>{ARTICLE_MODES[value]}</option>)}
            </select>
          </label>
          <label className="typing-checkbox">
            <input type="checkbox" checked={pinyin} onChange={event => {
              setError('')
              setConfig(previous => ({ ...previous, pinyin: event.target.checked }))
            }} />
            显示拼音
          </label>
          {mode === 'fixed' && availableGrades?.map(grade => (
            <fieldset className="typing-fixed-grade" key={grade.grade}>
              <legend>{grade.label}固定文章</legend>
              {LANGUAGES.map(language => <label key={language}>{LANGUAGE_NAMES[language]}
                <select value={validArticle(grade, language)} onChange={event => selectArticle(grade.grade, language, event.target.value)}>
                  <option value="">请选择文章</option>
                  {grade.articles[language].map(article => <option key={article.id} value={article.id}>{article.title}</option>)}
                </select>
              </label>)}
            </fieldset>
          ))}
        </fieldset>
        {((!config || (mode === 'fixed' && !availableGrades)) && !error) && <p role="status">正在读取设置…</p>}
        {error && <p role="alert" className="typing-error">{error}</p>}
        <div className="typing-dialog-actions">
          <button type="button" disabled={pending} onClick={() => close()}>取消</button>
          <button type="submit" className="typing-primary" disabled={!canSave || pending}>保存设置</button>
        </div>
      </form>
    </dialog>
  )
}
