import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, Award, CheckCircle, Code2, Loader, RotateCcw, XCircle } from 'lucide-react'
import Navbar from '../../../components/Navbar.jsx'
import RichQuestionText from '../../../components/RichQuestionText.jsx'
import { getCurrentUser } from '../../../api/index.js'
import { getAIQuizResult } from '../../../api/aiStudentQuiz.js'
import './aiQuiz.css'

const FINAL = new Set(['submitted', 'timed_out', 'closed'])
const reasonLabel = { submitted: '已交卷', timed_out: '时间到，已自动交卷', closed: '小测已关闭并结算' }

export default function AIQuizResult() {
  const { sessionId } = useParams()
  const user = getCurrentUser()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    let timer
    let attempts = 0
    const load = async () => {
      try {
        const data = await getAIQuizResult(sessionId)
        if (!alive) return
        setResult(data); setError(''); setLoading(false)
        if (!FINAL.has(data.status) && attempts < 60) { attempts += 1; timer = window.setTimeout(load, 1500) }
      } catch (reason) {
        if (!alive) return
        setError(`加载成绩失败：${reason.message}`); setLoading(false)
      }
    }
    load()
    return () => { alive = false; window.clearTimeout(timer) }
  }, [sessionId])

  if (loading) return <div className="page-bg"><Navbar username={user.display_name || user.username} grade={user.grade} class_num={user.class_num} /><div className="aiq-loading page"><Loader className="spin" />正在结算成绩…</div></div>
  if (error || !result) return <div className="page-bg"><Navbar username={user.display_name || user.username} grade={user.grade} class_num={user.class_num} /><div className="aiq-fatal"><p role="alert">{error}</p><Link className="btn btn-secondary" to="/student/dashboard?course=ai">返回小测列表</Link></div></div>
  if (!FINAL.has(result.status)) return <div className="page-bg"><Navbar username={user.display_name || user.username} grade={user.grade} class_num={user.class_num} /><main className="aiq-result-shell"><section className="aiq-card aiq-settling"><Loader className="spin" size={42} /><h1>评测结算中</h1><p>正在等待交卷前已受理的编程评测，页面会自动更新。</p></section></main></div>

  const wrongChoices = (result.choice_items || []).filter(item => !item.is_correct)
  const total = Number(result.scores?.total || 0)
  return <div className="page-bg aiq-page"><Navbar username={user.display_name || user.username} grade={user.grade} class_num={user.class_num} />
    <main className="aiq-result-shell">
      <section className="aiq-card aiq-result-overview">
        <Award size={46} color="#667eea" /><h1>{result.quiz.title}</h1><p>{reasonLabel[result.final_reason] || '已完成'} · 第 {result.attempt_no} 次作答</p>
        <div className="aiq-total-score"><strong>{total.toFixed(1)}</strong><span>/ 100</span></div>
        <div className="aiq-score-parts"><span>选择题 <strong>{result.scores.choice ?? '0.0'}</strong> 分</span><span>编程题 <strong>{result.scores.programming ?? '0.0'}</strong> 分</span><span>选择题正确 <strong>{result.choice_summary.correct_count ?? 0}/{result.choice_summary.question_count ?? 0}</strong></span></div>
      </section>
      {result.grading_issue_count > 0 && <div className="aiq-alert aiq-alert-warning"><AlertTriangle size={18} />有 {result.grading_issue_count} 道编程题评测异常，未按学生答错处理，请联系教师重评。</div>}
      {(result.programming_items || []).length > 0 && <section><h2 className="aiq-result-title"><Code2 />编程题成绩</h2><div className="aiq-result-grid">{result.programming_items.map(item => <article className="aiq-card aiq-program-score" key={item.item_id}><div><strong>{item.position}. {item.title}</strong><small>{item.submission_count ?? 0} 次有效提交</small></div>{item.status === 'system_issue' ? <span className="issue">评测异常，教师可重评</span> : <span><b>{item.best_score ?? 0}</b>/100 · 折算 {item.earned_points}/{item.points} 分</span>}</article>)}</div></section>}
      {wrongChoices.length > 0 && <section><h2 className="aiq-result-title"><XCircle />选择题解析</h2><div className="aiq-result-grid">{wrongChoices.map(item => <article className="aiq-card aiq-wrong-choice" key={item.item_id}><RichQuestionText value={item.text} className="aiq-stem" /><div className="aiq-review-options">{['A','B','C','D'].map(option => <div key={option} className={`${item.correct_option === option ? 'correct' : ''} ${item.selected_option === option && item.correct_option !== option ? 'wrong' : ''}`}><b>{option}.</b><RichQuestionText value={item.options?.[option] || ''} />{item.correct_option === option && <CheckCircle size={15} />}{item.selected_option === option && item.correct_option !== option && <XCircle size={15} />}</div>)}</div><p className="aiq-answer-note">你的答案：{item.selected_option || '未作答'}；正确答案：{item.correct_option}</p>{item.explanation && <div className="aiq-explanation"><strong>解析</strong><RichQuestionText value={item.explanation} /></div>}</article>)}</div></section>}
      <div className="aiq-result-actions"><Link className="btn btn-secondary" to="/student/dashboard?course=ai">返回小测列表</Link>{result.can_retry && <Link className="btn btn-primary" to={`/student/ai-quiz/${sessionId}`}><RotateCcw size={16} />再做一次</Link>}</div>
    </main>
  </div>
}
