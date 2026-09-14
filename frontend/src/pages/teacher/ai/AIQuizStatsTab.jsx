/* Data-loading effects intentionally synchronize this dashboard with server-side filters. */
/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Code2,
  Download,
  FileClock,
  HelpCircle,
  Loader,
  RefreshCw,
  Search,
  Users,
} from "lucide-react";

import { getAdminScores } from "../../../api/index.js";
import {
  getAIQuizAnalyticsItems,
  getAIQuizAnalyticsOverview,
  getAIQuizAnalyticsStudents,
  getAIQuizzes,
} from "../../../api/aiQuiz.js";
import RichQuestionText from "../../../components/RichQuestionText.jsx";
import { GRADES } from "../../../constants/grades.js";
import "./AIQuizStatsTab.css";

const LABEL = {
  not_started: "未开始",
  completed: "已完成",
  in_progress: "作答中",
  settling: "结算中",
  submitted: "已提交",
  timed_out: "已超时",
  closed: "关闭结算",
  reset: "已重置",
  superseded: "历史作答",
};
const score = (value) => (value == null ? "—" : `${value} 分`);

function initialLampThresholds() {
  try {
    return JSON.parse(localStorage.getItem("aiQuizLampThresholds") || "{}");
  } catch {
    return {};
  }
}

function Pager({ data, onPage }) {
  if (!data || data.pages <= 1) return null;
  return (
    <div className="ai-stats-pager">
      <button disabled={data.page <= 1} onClick={() => onPage(data.page - 1)}>
        <ChevronLeft size={15} />
        上一页
      </button>
      <span>
        第 {data.page}/{data.pages} 页，共 {data.total} 条
      </span>
      <button
        disabled={data.page >= data.pages}
        onClick={() => onPage(data.page + 1)}
      >
        下一页
        <ChevronRight size={15} />
      </button>
    </div>
  );
}

function PracticeStats() {
  const [filters, setFilters] = useState({
    grade: "",
    class_num: "",
    problem_id: "",
  });
  const [data, setData] = useState({ students: [], problems: [] });
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await getAdminScores({ ...filters, course_type: "ai" }));
    } finally {
      setLoading(false);
    }
  }, [filters]);
  useEffect(() => {
    load();
  }, [load]);
  const submissions = (data.students || []).flatMap(
    (student) => student.scores || [],
  );
  const average = submissions.length
    ? (
        submissions.reduce((sum, item) => sum + Number(item.score || 0), 0) /
        submissions.length
      ).toFixed(1)
    : "0.0";
  const scoreMapByNumber = useMemo(() => {
    const values = {};
    for (const student of data.students || []) {
      const number = Number.parseInt(student.student_number, 10);
      if (number >= 1 && number <= 50) {
        values[number] = Math.max(values[number] || 0, student.best_score || 0);
      }
    }
    return values;
  }, [data.students]);
  const perfectCount = Object.values(scoreMapByNumber).filter(
    (value) => value === 100,
  ).length;
  const set = (key, value) => setFilters((old) => ({ ...old, [key]: value }));
  return (
    <div className="ai-stats-stack">
      <div className="ai-stats-toolbar">
        <BookOpen size={18} />
        <strong>题库练习成绩</strong>
        <label>
          年级
          <select
            aria-label="成绩年级筛选"
            value={filters.grade}
            onChange={(event) => set("grade", event.target.value)}
          >
            <option value="">全部年级</option>
            {GRADES.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          班级
          <select
            aria-label="成绩班级筛选"
            value={filters.class_num}
            onChange={(event) => set("class_num", event.target.value)}
          >
            <option value="">全部班级</option>
            {Array.from({ length: 20 }, (_, index) => (
              <option key={index + 1} value={index + 1}>
                {index + 1}班
              </option>
            ))}
          </select>
        </label>
        <label>
          题目
          <select
            aria-label="成绩题目筛选"
            value={filters.problem_id}
            onChange={(event) => set("problem_id", event.target.value)}
          >
            <option value="">全部题目</option>
            {(data.problems || []).map((item) => (
              <option key={item.problem_id} value={item.problem_id}>
                {item.title || item.problem_id}
              </option>
            ))}
          </select>
        </label>
        <button onClick={load}>
          <RefreshCw size={14} />
          刷新
        </button>
      </div>
      <div className="ai-stats-summary">
        {[
          ["学生数", data.students?.length || 0],
          ["题目数", data.problems?.length || 0],
          ["已提交", submissions.length],
          ["平均分", average],
          ["满分人数", perfectCount],
        ].map(([label, value]) => (
          <div key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </div>
        ))}
      </div>
      <div className="ai-practice-body">
        <div className="ai-stats-panel ai-stats-table-wrap">
          {loading ? (
            <div className="ai-stats-loading">加载中…</div>
          ) : !data.students?.length ? (
            <div className="ai-stats-empty">暂无练习成绩</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>学生</th>
                  {data.problems.map((item) => (
                    <th key={item.problem_id}>
                      {item.title || item.problem_id}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.students.map((student, index) => {
                  const map = Object.fromEntries(
                    (student.scores || []).map((item) => [
                      item.problem_id,
                      item.score,
                    ]),
                  );
                  return (
                    <tr
                      key={
                        student.id ??
                        student.student_id ??
                        student.username ??
                        index
                      }
                      className={student.best_score === 100 ? "perfect" : ""}
                    >
                      <td>
                        <strong>
                          {student.display_name || student.username}
                        </strong>
                        <small>
                          {student.grade} {student.class_num}班
                        </small>
                      </td>
                      {data.problems.map((item) => (
                        <td key={item.problem_id}>
                          {map[item.problem_id] ?? "—"}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
        <aside className="ai-perfect-lamps" aria-label="满分监控学号1至50">
          <h3>满分监控 · 学号 1–50</h3>
          <div className="ai-perfect-lamp-grid">
            {Array.from({ length: 50 }, (_, index) => {
              const number = index + 1;
              const active = scoreMapByNumber[number] === 100;
              return (
                <div
                  key={number}
                  className={active ? "active" : ""}
                  title={`学号 ${number} · ${active ? "满分" : "未满分"}`}
                  aria-label={`学号 ${number}${active ? "已满分" : "未满分"}`}
                >
                  {number}
                </div>
              );
            })}
          </div>
          <p>
            <strong>{perfectCount}</strong>/50 满分
          </p>
        </aside>
      </div>
    </div>
  );
}

export default function AIQuizStatsTab() {
  const [mode, setMode] = useState("quiz");
  const [quizzes, setQuizzes] = useState([]);
  const [quizId, setQuizId] = useState("");
  const [view, setView] = useState("students");
  const [overview, setOverview] = useState(null);
  const [analysis, setAnalysis] = useState({
    choice_items: [],
    programming_items: [],
  });
  const [students, setStudents] = useState({
    results: [],
    lamp_students: [],
    pagination: null,
  });
  const [filters, setFilters] = useState({ grade: "", class_num: "" });
  const [applied, setApplied] = useState({ grade: "", class_num: "" });
  const [page, setPage] = useState(1);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lampThresholds, setLampThresholds] = useState(initialLampThresholds);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadQuizzes = useCallback(async () => {
    setLoading(true);
    try {
      const values = (await getAIQuizzes({ include_archived: true })).filter(
        (item) => item.blueprint_version > 0,
      );
      setQuizzes(values);
      setQuizId((old) => old || String(values[0]?.id || ""));
      setError("");
    } catch (reason) {
      setError(reason.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    loadQuizzes();
  }, [loadQuizzes]);
  const loadSummary = useCallback(async () => {
    if (!quizId) return;
    try {
      const [summary, items] = await Promise.all([
        getAIQuizAnalyticsOverview(quizId),
        getAIQuizAnalyticsItems(quizId),
      ]);
      setOverview(summary);
      setAnalysis(items);
      setError("");
    } catch (reason) {
      setError(reason.message);
    }
  }, [quizId]);
  const loadStudents = useCallback(
    async (silent = false) => {
      if (!quizId) return;
      if (!silent) setLoading(true);
      try {
        setStudents(
          await getAIQuizAnalyticsStudents(quizId, {
            ...applied,
            page,
            page_size: 20,
          }),
        );
        setError("");
      } catch (reason) {
        setError(reason.message);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [applied, page, quizId],
  );
  useEffect(() => {
    loadSummary();
  }, [loadSummary]);
  useEffect(() => {
    loadStudents();
  }, [loadStudents]);
  const refresh = useCallback(
    (silent = false) => Promise.all([loadSummary(), loadStudents(silent)]),
    [loadStudents, loadSummary],
  );
  useEffect(() => {
    if (!autoRefresh || mode !== "quiz" || !quizId) return undefined;
    const timer = window.setInterval(() => refresh(true), 5000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, mode, quizId, refresh]);
  const threshold = Number(lampThresholds[quizId] ?? 80);
  const setThreshold = (value) => {
    const nextValue = Math.min(100, Math.max(0, Number(value) || 0));
    setLampThresholds((current) => {
      const next = { ...current, [quizId]: nextValue };
      localStorage.setItem("aiQuizLampThresholds", JSON.stringify(next));
      return next;
    });
  };
  const exportRows = () => {
    const rows = [
      ["年级", "班级", "学号", "姓名", "历史最高成绩"],
      ...students.results.map((row) => [
        row.grade,
        row.class_num,
        row.student_number,
        row.display_name,
        row.best_total_score ?? "",
      ]),
    ];
    const csv =
      "\ufeff" +
      rows
        .map((values) =>
          values
            .map((value) => `"${String(value).replaceAll('"', '""')}"`)
            .join(","),
        )
        .join("\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `${overview?.quiz?.title || "AI小测"}-学生成绩.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };
  const cards = useMemo(
    () =>
      overview
        ? [
            ["应参与", overview.participation.expected],
            ["已开始", overview.participation.started],
            ["未开始", overview.participation.not_started],
            ["作答中", overview.participation.in_progress],
            ["已完成", overview.participation.submitted],
            ["平均分", overview.scores.average ?? "—"],
            [
              "及格率",
              overview.scores.pass_rate == null
                ? "—"
                : `${overview.scores.pass_rate}%`,
            ],
            ["最高分", overview.scores.highest ?? "—"],
          ]
        : [],
    [overview],
  );

  return (
    <section className="ai-stats-page">
      <header className="ai-stats-titlebar">
        <div>
          <BarChart3 />
          <div>
            <h2>AI课成绩统计</h2>
            <p>
              组合小测默认采用每位学生最近一次已结算成绩，并单独展示历史最好成绩。
            </p>
          </div>
        </div>
        <div className="ai-stats-mode" role="tablist" aria-label="成绩类型">
          <button
            role="tab"
            aria-selected={mode === "quiz"}
            className={mode === "quiz" ? "active" : ""}
            onClick={() => setMode("quiz")}
          >
            组合小测
          </button>
          <button
            role="tab"
            aria-selected={mode === "practice"}
            className={mode === "practice" ? "active" : ""}
            onClick={() => setMode("practice")}
          >
            题库练习
          </button>
        </div>
      </header>
      {mode === "practice" ? (
        <PracticeStats />
      ) : (
        <div className="ai-stats-stack">
          <div className="ai-stats-toolbar">
            <label className="ai-stats-quiz-select">
              选择小测
              <select
                aria-label="选择统计小测"
                value={quizId}
                onChange={(event) => {
                  setQuizId(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">请选择已发布小测</option>
                {quizzes.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}（{item.status === "open" ? "进行中" : "已关闭"}
                    ）
                  </option>
                ))}
              </select>
            </label>
            <label className="ai-auto-refresh">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(event) => setAutoRefresh(event.target.checked)}
              />
              每 5 秒自动刷新
            </label>
            <button disabled={!quizId} onClick={() => refresh(false)}>
              <RefreshCw size={14} />
              刷新统计
            </button>
          </div>
          {error && (
            <div role="alert" className="ai-stats-error">
              {error}
            </div>
          )}
          {!loading && !quizzes.length ? (
            <div className="ai-stats-panel ai-stats-empty">
              <FileClock />
              <h3>暂无已发布小测</h3>
            </div>
          ) : (
            <>
              <div className="ai-stats-summary">
                {cards.map(([label, value]) => (
                  <div key={label}>
                    <strong>{value}</strong>
                    <span>{label}</span>
                  </div>
                ))}
              </div>
              <div
                className="ai-stats-subtabs"
                role="tablist"
                aria-label="小测统计视图"
              >
                <button
                  role="tab"
                  aria-selected={view === "students"}
                  className={view === "students" ? "active" : ""}
                  onClick={() => setView("students")}
                >
                  <Users size={16} />
                  学生明细
                </button>
                <button
                  role="tab"
                  aria-selected={view === "items"}
                  className={view === "items" ? "active" : ""}
                  onClick={() => setView("items")}
                >
                  <HelpCircle size={16} />
                  题目分析
                </button>
              </div>
              {view === "students" ? (
                <StudentsPanel
                  loading={loading}
                  filters={filters}
                  setFilters={setFilters}
                  apply={() => {
                    setPage(1);
                    setApplied(filters);
                  }}
                  students={students}
                  setPage={setPage}
                  exportRows={exportRows}
                  threshold={threshold}
                  setThreshold={setThreshold}
                />
              ) : (
                <AnalysisPanel data={analysis} />
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}

function StudentsPanel({
  loading,
  filters,
  setFilters,
  apply,
  students,
  setPage,
  exportRows,
  threshold,
  setThreshold,
}) {
  const set = (key, value) => setFilters((old) => ({ ...old, [key]: value }));
  const lamps = useMemo(() => {
    const values = {};
    for (const student of students.lamp_students || students.results || []) {
      const number = Number.parseInt(student.student_number, 10);
      if (student.best_total_score == null) continue;
      const best = Number(student.best_total_score);
      if (number < 1 || number > 50 || !Number.isFinite(best)) continue;
      if (!values[number] || best > values[number].score) {
        values[number] = { score: best, student };
      }
    }
    return values;
  }, [students]);
  const litCount = Object.values(lamps).filter(
    (item) => item.score >= threshold,
  ).length;
  return (
    <div className="ai-stats-panel">
      <form
        className="ai-stats-filters"
        onSubmit={(event) => {
          event.preventDefault();
          apply();
        }}
      >
        <label>
          年级
          <select
            aria-label="小测年级筛选"
            value={filters.grade}
            onChange={(event) => set("grade", event.target.value)}
          >
            <option value="">全部年级</option>
            {GRADES.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          班级
          <select
            aria-label="小测班级筛选"
            value={filters.class_num}
            onChange={(event) => set("class_num", event.target.value)}
          >
            <option value="">全部班级</option>
            {Array.from({ length: 20 }, (_, index) => (
              <option key={index + 1} value={index + 1}>
                {index + 1}班
              </option>
            ))}
          </select>
        </label>
        <button type="submit">
          <Search size={14} />
          查询
        </button>
        <button
          type="button"
          disabled={!students.results.length}
          onClick={exportRows}
        >
          <Download size={14} />
          导出当前页
        </button>
      </form>
      <div className="ai-quiz-students-layout">
        <div className="ai-stats-table-wrap">
          {loading ? (
            <div className="ai-stats-loading">
              <Loader className="spin" />
              加载中…
            </div>
          ) : !students.results.length ? (
            <div className="ai-stats-empty">当前筛选下暂无学生</div>
          ) : (
            <table className="ai-quiz-student-table">
              <thead>
                <tr>
                  {["年级", "班级", "学号", "姓名", "历史最高成绩"].map(
                    (value) => (
                      <th key={value}>{value}</th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {students.results.map((row) => (
                  <tr key={row.student_id}>
                    <td>{row.grade || "—"}</td>
                    <td>{row.class_num ? `${row.class_num}班` : "—"}</td>
                    <td>{row.student_number || "—"}</td>
                    <td>{row.display_name}</td>
                    <td>{score(row.best_total_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Pager data={students.pagination} onPage={setPage} />
        </div>
        <aside className="ai-perfect-lamps" aria-label="小测亮灯矩阵学号1至50">
          <h3>小测达标矩阵 · 学号 1–50</h3>
          <label className="ai-lamp-threshold">
            亮灯阈值
            <input
              aria-label="亮灯阈值"
              type="number"
              min="0"
              max="100"
              step="1"
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
            />
            分
          </label>
          <div className="ai-perfect-lamp-grid">
            {Array.from({ length: 50 }, (_, index) => {
              const number = index + 1;
              const item = lamps[number];
              const active = Boolean(item && item.score >= threshold);
              const detail = item
                ? `${item.student.display_name} · 最高 ${item.score} 分`
                : "暂无成绩";
              return (
                <div
                  key={number}
                  className={active ? "active" : ""}
                  title={`学号 ${number} · ${detail}`}
                  aria-label={`学号 ${number}${active ? "已亮灯" : "未亮灯"}`}
                >
                  {number}
                </div>
              );
            })}
          </div>
          <p>
            <strong>{litCount}</strong>/50 已达到 {threshold} 分
          </p>
          {!filters.class_num && (
            <small>未筛选班级时，同学号取当前范围内的最高成绩。</small>
          )}
        </aside>
      </div>
    </div>
  );
}

function AnalysisPanel({ data }) {
  return (
    <div className="ai-analysis-grid">
      <section className="ai-stats-panel">
        <h3>
          <HelpCircle size={17} />
          选择题分析
        </h3>
        <div className="ai-choice-analysis">
          {!data.choice_items.length ? (
            <div className="ai-stats-empty">暂无选择题统计</div>
          ) : (
            data.choice_items.map((item, index) => (
              <article
                key={`${item.source_question_id}:${item.source_version}`}
              >
                <header>
                  <b>
                    {index + 1}. 正确率 {item.correct_rate ?? 0}%
                  </b>
                  <span>
                    {item.correct}/{item.response_count} 人答对 ·{" "}
                    {item.unanswered} 人未答
                  </span>
                </header>
                <RichQuestionText value={item.text} />
                <div className="ai-option-bars">
                  {"ABCD".split("").map((letter) => (
                    <div key={letter}>
                      <span
                        className={
                          letter === item.correct_option ? "correct" : ""
                        }
                      >
                        {letter}
                        {letter === item.correct_option ? "（正确）" : ""}
                      </span>
                      <div>
                        <i
                          style={{
                            width: `${item.response_count ? (item.option_counts[letter] * 100) / item.response_count : 0}%`,
                          }}
                        />
                      </div>
                      <b>{item.option_counts[letter]} 人</b>
                    </div>
                  ))}
                </div>
              </article>
            ))
          )}
        </div>
      </section>
      <section className="ai-stats-panel">
        <h3>
          <Code2 size={17} />
          编程题分析
        </h3>
        <div className="ai-program-analysis">
          {!data.programming_items.length ? (
            <div className="ai-stats-empty">暂无编程题统计</div>
          ) : (
            data.programming_items.map((item) => (
              <article key={item.item_id}>
                <header>
                  <strong>{item.title}</strong>
                  <span>{item.points} 分</span>
                </header>
                <div>
                  <b>{item.average_best_score ?? "—"}</b>
                  <span>平均最高分</span>
                </div>
                <dl>
                  <div>
                    <dt>提交人数</dt>
                    <dd>
                      {item.submitted_count}/{item.student_count}
                    </dd>
                  </div>
                  <div>
                    <dt>满分人数</dt>
                    <dd>{item.passed_count}</dd>
                  </div>
                  <div>
                    <dt>满分率</dt>
                    <dd>{item.pass_rate ?? 0}%</dd>
                  </div>
                  <div>
                    <dt>人均提交</dt>
                    <dd>{item.average_submission_count}</dd>
                  </div>
                </dl>
                <p>
                  常见结果：
                  {Object.entries(item.terminal_statuses || {})
                    .map(([key, value]) => `${key} ${value}次`)
                    .join(" · ") || "暂无提交"}
                </p>
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
