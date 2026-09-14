import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, BarChart3, BookOpen, Bot, ClipboardList, HelpCircle, Layers3 } from 'lucide-react'

import { getCurrentUser } from '../../api/index.js'
import AIChoiceQuestionsTab from './ai/AIChoiceQuestionsTab.jsx'
import AIProgrammingProblemsTab from './ai/AIProgrammingProblemsTab.jsx'
import AIQuizStatsTab from './ai/AIQuizStatsTab.jsx'
import AIQuizzesTab from './ai/AIQuizzesTab.jsx'
import AIUnitsTab from './ai/AIUnitsTab.jsx'

const TABS = [
  { key: 'units', label: '单元管理', icon: Layers3 },
  { key: 'choices', label: '选择题库', icon: HelpCircle },
  { key: 'problems', label: '编程题库', icon: BookOpen },
  { key: 'quizzes', label: '小测管理', icon: ClipboardList },
  { key: 'stats', label: '成绩统计', icon: BarChart3 },
]

export default function AiAdmin() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('units')
  const [currentUser] = useState(() => getCurrentUser())

  return <div style={{ minHeight: '100vh', background: '#f5f7fa', fontFamily: '"Microsoft JhengHei", Arial, sans-serif' }}>
    <header style={{ background: 'linear-gradient(135deg,#667eea 0%,#764ba2 100%)', color: '#fff', padding: '14px 0', boxShadow: '0 2px 10px rgba(0,0,0,.15)' }}>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
        <button onClick={() => navigate('/teacher/dashboard')} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,.15)', border: 0, borderRadius: 8, color: '#fff', cursor: 'pointer', padding: '7px 14px', fontWeight: 650 }}><ArrowLeft size={14} />返回主页</button>
        <span aria-hidden="true" style={{ width: 1, height: 24, background: 'rgba(255,255,255,.25)' }} />
        <Bot size={20} /><h1 style={{ margin: 0, fontSize: 20 }}>AI课管理</h1>
        <nav aria-label="AI课管理区域" role="tablist" style={{ marginLeft: 'auto', display: 'flex', gap: 4, background: 'rgba(255,255,255,.1)', borderRadius: 10, padding: 4, flexWrap: 'wrap' }}>
          {TABS.map(({ key, label, icon: Icon }) => <button key={key} role="tab" aria-selected={tab === key} aria-controls={`ai-tab-${key}`} onClick={() => setTab(key)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 13px', borderRadius: 8, border: 0, cursor: 'pointer', fontSize: 13, fontWeight: 700, background: tab === key ? '#fff' : 'transparent', color: tab === key ? '#667eea' : 'rgba(255,255,255,.78)' }}><Icon size={14} />{label}</button>)}
        </nav>
      </div>
    </header>
    <main style={{ maxWidth: 1400, margin: '0 auto', padding: '26px 24px' }}>
      <div id={`ai-tab-${tab}`} role="tabpanel">
        {tab === 'units' && <AIUnitsTab currentUser={currentUser} />}
        {tab === 'choices' && <AIChoiceQuestionsTab currentUser={currentUser} />}
        {tab === 'problems' && <AIProgrammingProblemsTab currentUser={currentUser} />}
        {tab === 'quizzes' && <AIQuizzesTab currentUser={currentUser} />}
        {tab === 'stats' && <AIQuizStatsTab />}
      </div>
    </main>
  </div>
}
