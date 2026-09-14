import { useEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  ClipboardList,
  Copy,
  Edit2,
  Eye,
  LockKeyhole,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Settings2,
  Trash2,
  X,
} from "lucide-react";

import {
  getAdminProblems,
  getProblemClassOptions,
} from "../../../api/index.js";
import {
  closeAIQuiz,
  copyAIQuiz,
  createAIQuiz,
  deleteAIQuiz,
  getAIChoiceQuestions,
  getAIQuizzes,
  getAIUnits,
  publishAIQuiz,
  reopenAIQuiz,
  updateAIQuiz,
  updateAIQuizAudience,
  validateAIQuiz,
} from "../../../api/aiQuiz.js";
import { GRADES } from "../../../constants/grades.js";

const panel = {
  background: "#fff",
  borderRadius: 14,
  boxShadow: "0 2px 8px rgba(0,0,0,.06)",
};
const input = {
  minHeight: 38,
  padding: "8px 11px",
  border: "1px solid #d9deea",
  borderRadius: 8,
  font: "inherit",
  fontSize: 13,
  background: "#fff",
  color: "#333",
  outlineColor: "#667eea",
};
const primary = {
  border: 0,
  borderRadius: 8,
  padding: "9px 15px",
  background: "#667eea",
  color: "#fff",
  fontWeight: 700,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 6,
};
const secondary = {
  border: "1px solid #d9deea",
  borderRadius: 8,
  padding: "8px 13px",
  background: "#fff",
  color: "#4e5666",
  fontWeight: 650,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 6,
};
const STEPS = [
  "基本信息",
  "选择题组卷",
  "编程题组卷",
  "分值与发布范围",
  "预览并保存",
];
const STATUS = {
  draft: { label: "草稿", bg: "#fff4dc", color: "#8a5a00" },
  open: { label: "进行中", bg: "#e6f7ed", color: "#18794e" },
  closed: { label: "已关闭", bg: "#eef1ff", color: "#5369d8" },
};

function ModalShell({ title, children, onClose, width = 980 }) {
  return (
    <div
      role="presentation"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(26,32,50,.55)",
        display: "grid",
        placeItems: "center",
        padding: 20,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{
          width: `min(${width}px,100%)`,
          maxHeight: "calc(100vh - 40px)",
          overflow: "auto",
          borderRadius: 16,
          background: "#f7f8fc",
          boxShadow: "0 28px 80px rgba(19,25,48,.3)",
        }}
      >
        <div
          style={{
            position: "sticky",
            top: 0,
            zIndex: 2,
            background: "#fff",
            borderBottom: "1px solid #e8ebf2",
            padding: "16px 20px",
            display: "flex",
            alignItems: "center",
          }}
        >
          <h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>
          <button
            type="button"
            aria-label={`关闭${title}`}
            onClick={onClose}
            style={{
              marginLeft: "auto",
              border: 0,
              borderRadius: 8,
              background: "#f1f3f8",
              width: 32,
              height: 32,
              display: "grid",
              placeItems: "center",
              cursor: "pointer",
            }}
          >
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Notice({ value }) {
  if (!value.text) return null;
  return (
    <div
      role={value.type === "error" ? "alert" : "status"}
      style={{
        padding: "11px 14px",
        borderRadius: 9,
        background: value.type === "error" ? "#ffeaec" : "#e6f7ed",
        color: value.type === "error" ? "#a61b29" : "#18794e",
        whiteSpace: "pre-wrap",
      }}
    >
      {value.text}
    </div>
  );
}

function audienceFrom(mode, grade, classes) {
  if (mode === "all_school") return [{ scope_type: "all_school" }];
  if (mode === "classes")
    return classes.map((classNum) => ({
      scope_type: "class",
      grade,
      class_num: classNum,
    }));
  return [{ scope_type: "grade_all", grade }];
}

function audienceState(rules = []) {
  if (rules.some((rule) => rule.scope_type === "all_school"))
    return { mode: "all_school", classes: [] };
  const classes = rules
    .filter((rule) => rule.scope_type === "class" && rule.is_active !== false)
    .map((rule) => String(rule.class_num));
  return { mode: classes.length ? "classes" : "grade_all", classes };
}

function AudienceFields({
  currentUser,
  grade,
  mode,
  classes,
  classOptions,
  onMode,
  onClasses,
}) {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div
        role="radiogroup"
        aria-label="小测发布范围"
        style={{ display: "flex", flexWrap: "wrap", gap: 10 }}
      >
        <label
          style={{
            ...secondary,
            cursor: "pointer",
            background: mode === "grade_all" ? "#eef1ff" : "#fff",
            borderColor: mode === "grade_all" ? "#667eea" : "#d9deea",
          }}
        >
          <input
            type="radio"
            name="audience"
            checked={mode === "grade_all"}
            onChange={() => onMode("grade_all")}
          />
          {grade}全年级
        </label>
        <label
          style={{
            ...secondary,
            cursor: "pointer",
            background: mode === "classes" ? "#eef1ff" : "#fff",
            borderColor: mode === "classes" ? "#667eea" : "#d9deea",
          }}
        >
          <input
            type="radio"
            name="audience"
            checked={mode === "classes"}
            onChange={() => onMode("classes")}
          />
          指定班级
        </label>
        {currentUser?.is_superuser && (
          <label
            style={{
              ...secondary,
              cursor: "pointer",
              background: mode === "all_school" ? "#eef1ff" : "#fff",
              borderColor: mode === "all_school" ? "#667eea" : "#d9deea",
            }}
          >
            <input
              type="radio"
              name="audience"
              checked={mode === "all_school"}
              onChange={() => onMode("all_school")}
            />
            全校
          </label>
        )}
      </div>
      {mode === "classes" && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {classOptions.length ? (
            classOptions.map((classNum) => (
              <label
                key={classNum}
                style={{
                  padding: "7px 11px",
                  borderRadius: 8,
                  border: `1px solid ${classes.includes(String(classNum)) ? "#667eea" : "#d9deea"}`,
                  background: classes.includes(String(classNum))
                    ? "#eef1ff"
                    : "#fff",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                <input
                  type="checkbox"
                  checked={classes.includes(String(classNum))}
                  onChange={(event) =>
                    onClasses(
                      event.target.checked
                        ? [...classes, String(classNum)]
                        : classes.filter((item) => item !== String(classNum)),
                    )
                  }
                />{" "}
                {classNum}班
              </label>
            ))
          ) : (
            <span style={{ color: "#8a5a00", fontSize: 13 }}>
              该年级暂无可选的启用学生班级。
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function QuizWizard({ currentUser, quiz, onClose, onSaved }) {
  const editing = Boolean(quiz?.id);
  const allowedGrades = currentUser?.is_superuser
    ? GRADES
    : [currentUser?.managed_grade || GRADES[0]];
  const initialAudience = audienceState(quiz?.audience);
  const [step, setStep] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadingBank, setLoadingBank] = useState(true);
  const [error, setError] = useState("");
  const [units, setUnits] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [problems, setProblems] = useState([]);
  const [classes, setClasses] = useState([]);
  const [problemQuery, setProblemQuery] = useState("");
  const [problemUnit, setProblemUnit] = useState("");
  const [problemPage, setProblemPage] = useState(1);
  const [form, setForm] = useState({
    title: quiz?.title || "",
    content_grade: quiz?.content_grade || allowedGrades[0],
    time_limit: quiz?.time_limit ?? 45,
    choice_unit_ids: quiz?.choice_unit_ids || [],
    choice_question_count: quiz?.choice_question_count || 0,
    choice_difficulty_ratio: {
      easy: 0,
      medium: 0,
      hard: 0,
      ...(quiz?.choice_difficulty_ratio || {}),
    },
    choice_points: Number(quiz?.choice_points || 0),
    programming_items: [...(quiz?.programming_items || [])]
      .sort((a, b) => a.position - b.position)
      .map((item) => ({
        problem_id: item.problem_id,
        position: item.position,
        points: Number(item.points),
      })),
    audienceMode: initialAudience.mode,
    audienceClasses: initialAudience.classes,
  });
  const set = (key, value) => {
    setDirty(true);
    setForm((current) => ({ ...current, [key]: value }));
  };
  const close = () => {
    if (!dirty || window.confirm("尚有未保存的组卷修改，确定关闭吗？"))
      onClose();
  };

  useEffect(() => {
    if (!dirty) return undefined;
    const guard = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty]);

  useEffect(() => {
    let alive = true;
    Promise.all([
      getAIUnits({ grade: form.content_grade }),
      getAIChoiceQuestions({ grade: form.content_grade, status: "active" }),
      getAdminProblems(),
      getProblemClassOptions(form.content_grade),
    ])
      .then(([unitData, questionData, problemData, classData]) => {
        if (!alive) return;
        setUnits(unitData);
        setQuestions(questionData);
        setProblems(problemData);
        setClasses(classData.classes || []);
      })
      .catch((reason) => alive && setError(reason.message))
      .finally(() => alive && setLoadingBank(false));
    return () => {
      alive = false;
    };
  }, [form.content_grade]);

  const sections = useMemo(
    () =>
      units.flatMap((root) =>
        (root.sections || [])
          .filter((section) => !section.archived_at)
          .map((section) => ({ ...section, rootName: root.display_name })),
      ),
    [units],
  );
  const available = useMemo(() => {
    const selected = new Set(form.choice_unit_ids.map(Number));
    return questions
      .filter((question) => selected.has(Number(question.unit)))
      .reduce(
        (counts, question) => ({
          ...counts,
          [question.difficulty]: (counts[question.difficulty] || 0) + 1,
        }),
        { easy: 0, medium: 0, hard: 0 },
      );
  }, [form.choice_unit_ids, questions]);
  const selectedIds = new Set(
    form.programming_items.map((item) => item.problem_id),
  );
  const eligibleProblems = problems.filter(
    (problem) =>
      problem.grade_tag === form.content_grade && problem.quiz_usable,
  );
  const visibleProblems = eligibleProblems.filter(
    (problem) =>
      (!problemUnit || String(problem.unit) === problemUnit) &&
      (!problemQuery ||
        `${problem.title} ${problem.problem_id}`
          .toLowerCase()
          .includes(problemQuery.toLowerCase())),
  );
  const problemPageCount = Math.max(1, Math.ceil(visibleProblems.length / 8));
  const pagedProblems = visibleProblems.slice(
    (problemPage - 1) * 8,
    problemPage * 8,
  );
  const programmingPoints = form.programming_items.reduce(
    (sum, item) => sum + Number(item.points || 0),
    0,
  );
  const totalPoints = Number(form.choice_points || 0) + programmingPoints;
  const difficultyTotal = Object.values(form.choice_difficulty_ratio).reduce(
    (sum, value) => sum + Number(value || 0),
    0,
  );
  const poolIssues = loadingBank
    ? []
    : [
        ["easy", "容易"],
        ["medium", "中等"],
        ["hard", "困难"],
      ]
        .filter(
          ([key]) => Number(form.choice_difficulty_ratio[key]) > available[key],
        )
        .map(
          ([key, label]) =>
            `${label}题题池不足：需要 ${form.choice_difficulty_ratio[key]} 道，当前可用 ${available[key]} 道`,
        );
  const localIssues = [
    !form.title.trim() && "请填写小测名称",
    (Number(form.time_limit) < 1 || Number(form.time_limit) > 600) &&
      "时长必须在 1–600 分钟之间",
    form.choice_question_count > 0 &&
      !form.choice_unit_ids.length &&
      "选择题需要至少选择一个小节",
    difficultyTotal !== Number(form.choice_question_count) &&
      "容易、中等、困难题数之和必须等于选择题总数",
    Number(form.choice_question_count) === 0 &&
      Number(form.choice_points) !== 0 &&
      "不抽选择题时，选择题分值必须为 0",
    form.choice_question_count === 0 &&
      !form.programming_items.length &&
      "小测至少需要一种题型",
    form.programming_items.some((item) => Number(item.points) <= 0) &&
      "每道编程题分值必须大于 0",
    Math.abs(totalPoints - 100) > 0.001 &&
      `小测总分必须为 100，当前为 ${totalPoints.toFixed(1)} 分`,
    form.audienceMode === "classes" &&
      !form.audienceClasses.length &&
      "指定班级时至少选择一个班级",
    ...poolIssues,
  ].filter(Boolean);

  const toggleUnit = (id) =>
    set(
      "choice_unit_ids",
      form.choice_unit_ids.includes(id)
        ? form.choice_unit_ids.filter((item) => item !== id)
        : [...form.choice_unit_ids, id],
    );
  const toggleRoot = (root) => {
    const ids = (root.sections || [])
      .filter((section) => !section.archived_at)
      .map((section) => section.id);
    const all =
      ids.length && ids.every((id) => form.choice_unit_ids.includes(id));
    set(
      "choice_unit_ids",
      all
        ? form.choice_unit_ids.filter((id) => !ids.includes(id))
        : [...new Set([...form.choice_unit_ids, ...ids])],
    );
  };
  const setDifficulty = (key, value) =>
    set("choice_difficulty_ratio", {
      ...form.choice_difficulty_ratio,
      [key]: Math.max(0, Number(value) || 0),
    });
  const addProblem = (problem) =>
    set("programming_items", [
      ...form.programming_items,
      {
        problem_id: problem.problem_id,
        position: form.programming_items.length + 1,
        points: 0,
      },
    ]);
  const removeProblem = (problemId) =>
    set(
      "programming_items",
      form.programming_items
        .filter((item) => item.problem_id !== problemId)
        .map((item, index) => ({ ...item, position: index + 1 })),
    );
  const moveProblem = (index, direction) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= form.programming_items.length) return;
    const next = [...form.programming_items];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    set(
      "programming_items",
      next.map((item, position) => ({ ...item, position: position + 1 })),
    );
  };
  const setProblemPoints = (problemId, points) =>
    set(
      "programming_items",
      form.programming_items.map((item) =>
        item.problem_id === problemId
          ? { ...item, points: Number(points) || 0 }
          : item,
      ),
    );
  const changeGrade = (grade) => {
    setDirty(true);
    setLoadingBank(true);
    setProblemUnit("");
    setProblemQuery("");
    setProblemPage(1);
    setForm((current) => ({
      ...current,
      content_grade: grade,
      choice_unit_ids: [],
      programming_items: [],
      audienceMode: "grade_all",
      audienceClasses: [],
    }));
  };
  const payload = () => ({
    title: form.title.trim(),
    content_grade: form.content_grade,
    time_limit: Number(form.time_limit),
    choice_unit_ids: Number(form.choice_question_count)
      ? form.choice_unit_ids
      : [],
    choice_question_count: Number(form.choice_question_count),
    choice_difficulty_ratio: Number(form.choice_question_count)
      ? Object.fromEntries(
          Object.entries(form.choice_difficulty_ratio).map(([key, value]) => [
            key,
            Number(value),
          ]),
        )
      : { easy: 0, medium: 0, hard: 0 },
    choice_points: Number(form.choice_question_count)
      ? Number(form.choice_points).toFixed(1)
      : "0.0",
    programming_items: form.programming_items.map((item, index) => ({
      problem_id: item.problem_id,
      position: index + 1,
      points: Number(item.points).toFixed(1),
    })),
    audience: audienceFrom(
      form.audienceMode,
      form.content_grade,
      form.audienceClasses,
    ),
  });
  const save = async () => {
    if (localIssues.length) {
      setError(localIssues.join("\n"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      const saved = editing
        ? await updateAIQuiz(quiz.id, {
            ...payload(),
            expected_version: quiz.management_version,
          })
        : await createAIQuiz(payload());
      setDirty(false);
      onSaved(saved);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setSaving(false);
    }
  };

  const renderStep = () => {
    if (step === 0)
      return (
        <div style={{ display: "grid", gap: 16, maxWidth: 620 }}>
          <label
            style={{ display: "grid", gap: 6, fontWeight: 700, fontSize: 13 }}
          >
            小测名称
            <input
              autoFocus
              aria-label="小测名称"
              value={form.title}
              onChange={(event) => set("title", event.target.value)}
              style={input}
              placeholder="如：人工智能基础单元测试"
            />
          </label>
          <div
            style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}
          >
            <label
              style={{ display: "grid", gap: 6, fontWeight: 700, fontSize: 13 }}
            >
              内容年级
              <select
                aria-label="小测内容年级"
                value={form.content_grade}
                onChange={(event) => changeGrade(event.target.value)}
                style={input}
              >
                {allowedGrades.map((grade) => (
                  <option key={grade}>{grade}</option>
                ))}
              </select>
            </label>
            <label
              style={{ display: "grid", gap: 6, fontWeight: 700, fontSize: 13 }}
            >
              限时（分钟）
              <input
                aria-label="小测时长"
                type="number"
                min="1"
                max="600"
                value={form.time_limit}
                onChange={(event) => set("time_limit", event.target.value)}
                style={input}
              />
            </label>
          </div>
          <div
            style={{
              padding: 13,
              borderRadius: 9,
              background: "#eef1ff",
              color: "#53609b",
              fontSize: 13,
            }}
          >
            首次发布后，题目组成、分值和时长将锁定。如需改动，请复制为新小测。
          </div>
        </div>
      );
    if (step === 1)
      return (
        <div style={{ display: "grid", gap: 16 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.5fr 1fr",
              gap: 18,
            }}
          >
            <div style={{ display: "grid", gap: 10 }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>选择题小节（可多选）</h3>
              {loadingBank ? (
                <span>正在加载题库…</span>
              ) : units.length ? (
                units.map((root) => (
                  <div
                    key={root.id}
                    style={{
                      border: "1px solid #e1e5ed",
                      borderRadius: 10,
                      padding: 12,
                    }}
                  >
                    <label style={{ fontWeight: 750, cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        aria-label={`选择${root.display_name}全部小节`}
                        checked={
                          (root.sections || []).length > 0 &&
                          root.sections
                            .filter((section) => !section.archived_at)
                            .every((section) =>
                              form.choice_unit_ids.includes(section.id),
                            )
                        }
                        onChange={() => toggleRoot(root)}
                      />{" "}
                      {root.display_name}
                    </label>
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        flexWrap: "wrap",
                        marginTop: 9,
                      }}
                    >
                      {(root.sections || [])
                        .filter((section) => !section.archived_at)
                        .map((section) => (
                          <label
                            key={section.id}
                            style={{
                              padding: "6px 9px",
                              borderRadius: 8,
                              background: form.choice_unit_ids.includes(
                                section.id,
                              )
                                ? "#eef1ff"
                                : "#f7f8fa",
                              color: form.choice_unit_ids.includes(section.id)
                                ? "#5369d8"
                                : "#5e6675",
                              cursor: "pointer",
                              fontSize: 12,
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={form.choice_unit_ids.includes(
                                section.id,
                              )}
                              onChange={() => toggleUnit(section.id)}
                            />{" "}
                            {section.display_name}
                          </label>
                        ))}
                    </div>
                  </div>
                ))
              ) : (
                <span style={{ color: "#8a5a00" }}>该年级还没有可用小节。</span>
              )}
            </div>
            <div
              style={{
                ...panel,
                boxShadow: "none",
                border: "1px solid #e5e8ef",
                padding: 16,
                display: "grid",
                gap: 12,
                alignContent: "start",
              }}
            >
              <label
                style={{
                  display: "grid",
                  gap: 5,
                  fontSize: 13,
                  fontWeight: 700,
                }}
              >
                抽题总数
                <input
                  aria-label="选择题抽题数"
                  type="number"
                  min="0"
                  value={form.choice_question_count}
                  onChange={(event) =>
                    set(
                      "choice_question_count",
                      Math.max(0, Number(event.target.value) || 0),
                    )
                  }
                  style={input}
                />
              </label>
              {[
                ["easy", "容易"],
                ["medium", "中等"],
                ["hard", "困难"],
              ].map(([key, label]) => (
                <label
                  key={key}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 90px",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 13,
                  }}
                >
                  <span>
                    {label}{" "}
                    <small
                      style={{
                        color:
                          available[key] < form.choice_difficulty_ratio[key]
                            ? "#b3313d"
                            : "#7a8190",
                      }}
                    >
                      可用 {available[key]}
                    </small>
                  </span>
                  <input
                    aria-label={`${label}题数`}
                    type="number"
                    min="0"
                    value={form.choice_difficulty_ratio[key]}
                    onChange={(event) => setDifficulty(key, event.target.value)}
                    style={input}
                  />
                </label>
              ))}
              <div
                style={{
                  borderTop: "1px solid #e8ebf1",
                  paddingTop: 10,
                  fontSize: 12,
                  color:
                    difficultyTotal === Number(form.choice_question_count)
                      ? "#18794e"
                      : "#b3313d",
                }}
              >
                难度合计 {difficultyTotal} / {form.choice_question_count} 题
              </div>
            </div>
          </div>
        </div>
      );
    if (step === 2)
      return (
        <div
          style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 18 }}
        >
          <div style={{ display: "grid", gap: 10, alignContent: "start" }}>
            <div style={{ display: "flex", gap: 8 }}>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  flex: 1,
                }}
              >
                <Search size={15} />
                <input
                  aria-label="搜索编程题"
                  value={problemQuery}
                  onChange={(event) => {
                    setProblemQuery(event.target.value);
                    setProblemPage(1);
                  }}
                  style={{ ...input, flex: 1 }}
                  placeholder="搜索标题或编号"
                />
              </label>
              <select
                aria-label="编程题小节筛选"
                value={problemUnit}
                onChange={(event) => {
                  setProblemUnit(event.target.value);
                  setProblemPage(1);
                }}
                style={input}
              >
                <option value="">全部小节</option>
                {sections.map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.rootName} / {section.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div
              style={{
                maxHeight: 390,
                overflow: "auto",
                display: "grid",
                gap: 8,
              }}
            >
              {loadingBank ? (
                <span>正在加载题库…</span>
              ) : visibleProblems.length ? (
                pagedProblems.map((problem) => (
                  <div
                    key={problem.problem_id}
                    style={{
                      border: "1px solid #e1e5ed",
                      borderRadius: 9,
                      padding: 11,
                      display: "flex",
                      gap: 10,
                      alignItems: "center",
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <strong style={{ fontSize: 13 }}>
                        {problem.title || problem.problem_id}
                      </strong>
                      <div
                        style={{ fontSize: 11, color: "#7a8190", marginTop: 3 }}
                      >
                        {problem.problem_id} · {problem.big_unit_name} /{" "}
                        {problem.unit_name} ·{" "}
                        {problem.difficulty || "未设置难度"} ·{" "}
                        {problem.test_count} 个测试点
                      </div>
                    </div>
                    <button
                      type="button"
                      aria-label={`加入${problem.title || problem.problem_id}`}
                      disabled={selectedIds.has(problem.problem_id)}
                      onClick={() => addProblem(problem)}
                      style={{
                        ...secondary,
                        opacity: selectedIds.has(problem.problem_id) ? 0.55 : 1,
                      }}
                    >
                      {selectedIds.has(problem.problem_id) ? "已选" : "加入"}
                    </button>
                  </div>
                ))
              ) : (
                <div
                  style={{
                    padding: 24,
                    textAlign: "center",
                    color: "#8a5a00",
                    background: "#fff8e8",
                    borderRadius: 9,
                  }}
                >
                  当前年级暂无“已归类且有有效测试点”的可组卷编程题。
                </div>
              )}
            </div>
            {visibleProblems.length > 8 && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <button
                  type="button"
                  disabled={problemPage === 1}
                  onClick={() => setProblemPage((page) => page - 1)}
                  style={secondary}
                >
                  上一页
                </button>
                <span style={{ fontSize: 12 }}>
                  {problemPage} / {problemPageCount}
                </span>
                <button
                  type="button"
                  disabled={problemPage === problemPageCount}
                  onClick={() => setProblemPage((page) => page + 1)}
                  style={secondary}
                >
                  下一页
                </button>
              </div>
            )}
          </div>
          <div style={{ display: "grid", gap: 8, alignContent: "start" }}>
            <h3 style={{ margin: 0, fontSize: 14 }}>
              已选编程题（{form.programming_items.length}）
            </h3>
            {form.programming_items.length ? (
              form.programming_items.map((item, index) => {
                const problem =
                  problems.find(
                    (candidate) => candidate.problem_id === item.problem_id,
                  ) || item;
                return (
                  <div
                    key={item.problem_id}
                    style={{
                      border: "1px solid #dfe3ed",
                      background: "#fff",
                      borderRadius: 9,
                      padding: 10,
                      display: "grid",
                      gridTemplateColumns: "28px 1fr 92px auto",
                      gap: 8,
                      alignItems: "center",
                    }}
                  >
                    <strong style={{ color: "#667eea" }}>{index + 1}</strong>
                    <span
                      style={{ minWidth: 0, fontSize: 12, fontWeight: 700 }}
                    >
                      {problem.title || item.problem_id}
                    </span>
                    <label style={{ fontSize: 11 }}>
                      <input
                        aria-label={`${problem.title || item.problem_id}分值`}
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={item.points}
                        onChange={(event) =>
                          setProblemPoints(item.problem_id, event.target.value)
                        }
                        style={{ ...input, width: 72 }}
                      />{" "}
                      分
                    </label>
                    <div style={{ display: "flex", gap: 3 }}>
                      <button
                        type="button"
                        aria-label={`上移${problem.title || item.problem_id}`}
                        disabled={index === 0}
                        onClick={() => moveProblem(index, -1)}
                        style={{ ...secondary, padding: 5 }}
                      >
                        <ArrowUp size={14} />
                      </button>
                      <button
                        type="button"
                        aria-label={`下移${problem.title || item.problem_id}`}
                        disabled={index === form.programming_items.length - 1}
                        onClick={() => moveProblem(index, 1)}
                        style={{ ...secondary, padding: 5 }}
                      >
                        <ArrowDown size={14} />
                      </button>
                      <button
                        type="button"
                        aria-label={`移除${problem.title || item.problem_id}`}
                        onClick={() => removeProblem(item.problem_id)}
                        style={{ ...secondary, padding: 5, color: "#b3313d" }}
                      >
                        <X size={14} />
                      </button>
                    </div>
                  </div>
                );
              })
            ) : (
              <div
                style={{
                  padding: 25,
                  textAlign: "center",
                  color: "#7a8190",
                  border: "1px dashed #ccd2df",
                  borderRadius: 9,
                }}
              >
                可以不选编程题，或从左侧加入多道。
              </div>
            )}
          </div>
        </div>
      );
    if (step === 3)
      return (
        <div style={{ display: "grid", gap: 20 }}>
          <div
            style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}
          >
            <label
              style={{ display: "grid", gap: 6, fontSize: 13, fontWeight: 700 }}
            >
              选择题总分
              <input
                aria-label="选择题总分"
                type="number"
                min="0"
                max="100"
                step="0.1"
                disabled={!form.choice_question_count}
                value={form.choice_points}
                onChange={(event) =>
                  set("choice_points", Number(event.target.value) || 0)
                }
                style={input}
              />
            </label>
            <div
              style={{
                padding: 13,
                border: "1px solid #e1e5ed",
                borderRadius: 9,
              }}
            >
              <div style={{ color: "#7a8190", fontSize: 12 }}>编程题总分</div>
              <strong style={{ fontSize: 22, color: "#5369d8" }}>
                {programmingPoints.toFixed(1)}
              </strong>
            </div>
          </div>
          <div>
            <h3 style={{ fontSize: 14 }}>学生可见范围</h3>
            <AudienceFields
              currentUser={currentUser}
              grade={form.content_grade}
              mode={form.audienceMode}
              classes={form.audienceClasses}
              classOptions={classes}
              onMode={(value) => set("audienceMode", value)}
              onClasses={(value) => set("audienceClasses", value)}
            />
          </div>
          <div
            role="status"
            style={{
              padding: 15,
              borderRadius: 10,
              background:
                Math.abs(totalPoints - 100) < 0.001 ? "#e6f7ed" : "#fff4dc",
              color:
                Math.abs(totalPoints - 100) < 0.001 ? "#18794e" : "#8a5a00",
              fontWeight: 750,
            }}
          >
            当前总分：{totalPoints.toFixed(1)} / 100.0 分
          </div>
        </div>
      );
    return (
      <div style={{ display: "grid", gap: 16 }}>
        <div
          style={{
            ...panel,
            boxShadow: "none",
            border: "1px solid #e1e5ed",
            padding: 18,
          }}
        >
          <h3 style={{ margin: "0 0 12px" }}>{form.title || "未命名小测"}</h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4,minmax(120px,1fr))",
              gap: 10,
            }}
          >
            {[
              ["内容年级", form.content_grade],
              [
                "总题数",
                `${Number(form.choice_question_count) + form.programming_items.length} 题`,
              ],
              ["总分", `${totalPoints.toFixed(1)} 分`],
              ["限时", `${form.time_limit} 分钟`],
            ].map(([label, value]) => (
              <div
                key={label}
                style={{ padding: 12, borderRadius: 9, background: "#f5f6fb" }}
              >
                <small style={{ color: "#7a8190" }}>{label}</small>
                <strong style={{ display: "block", marginTop: 4 }}>
                  {value}
                </strong>
              </div>
            ))}
          </div>
          <p style={{ margin: "14px 0 0", color: "#596172" }}>
            选择题 {form.choice_question_count} 道 /{" "}
            {Number(form.choice_points).toFixed(1)} 分；编程题{" "}
            {form.programming_items.length} 道 / {programmingPoints.toFixed(1)}{" "}
            分。
          </p>
        </div>
        {localIssues.length ? (
          <div
            role="alert"
            style={{
              background: "#fff4dc",
              color: "#8a5a00",
              padding: 14,
              borderRadius: 9,
            }}
          >
            <strong>保存前请修正：</strong>
            <ul style={{ margin: "8px 0 0 20px" }}>
              {localIssues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        ) : (
          <div
            role="status"
            style={{
              background: "#e6f7ed",
              color: "#18794e",
              padding: 14,
              borderRadius: 9,
              display: "flex",
              gap: 8,
            }}
          >
            <Check size={18} />
            本地配置检查通过。保存草稿后，请在列表执行发布预检。
          </div>
        )}
      </div>
    );
  };

  return (
    <ModalShell
      title={editing ? "编辑小测草稿" : "新建 AI 小测"}
      onClose={close}
    >
      <div
        style={{
          padding: "18px 22px 0",
          display: "grid",
          gridTemplateColumns: "repeat(5,1fr)",
          gap: 6,
        }}
      >
        {STEPS.map((label, index) => (
          <button
            key={label}
            type="button"
            onClick={() => setStep(index)}
            aria-current={step === index ? "step" : undefined}
            style={{
              border: 0,
              borderRadius: 8,
              padding: "9px 6px",
              background:
                step === index
                  ? "#667eea"
                  : index < step
                    ? "#e6f7ed"
                    : "#eceff5",
              color:
                step === index ? "#fff" : index < step ? "#18794e" : "#697182",
              fontWeight: 700,
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            {index + 1}. {label}
          </button>
        ))}
      </div>
      <div style={{ padding: 22, minHeight: 420 }}>
        {error && (
          <div style={{ marginBottom: 14 }}>
            <Notice value={{ type: "error", text: error }} />
          </div>
        )}
        {renderStep()}
      </div>
      <div
        style={{
          position: "sticky",
          bottom: 0,
          background: "#fff",
          borderTop: "1px solid #e5e8ef",
          padding: "14px 20px",
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <button
          type="button"
          onClick={() => (step ? setStep(step - 1) : close())}
          style={secondary}
        >
          {step ? (
            <>
              <ChevronLeft size={15} />
              上一步
            </>
          ) : (
            "取消"
          )}
        </button>
        {step < STEPS.length - 1 ? (
          <button
            type="button"
            onClick={() => {
              setError("");
              setStep(step + 1);
            }}
            style={primary}
          >
            下一步
            <ChevronRight size={15} />
          </button>
        ) : (
          <button
            type="button"
            disabled={saving || localIssues.length > 0}
            onClick={save}
            style={{
              ...primary,
              opacity: saving || localIssues.length ? 0.55 : 1,
              cursor: saving || localIssues.length ? "not-allowed" : "pointer",
            }}
          >
            <ClipboardCheck size={15} />
            {saving ? "保存中…" : "保存草稿"}
          </button>
        )}
      </div>
    </ModalShell>
  );
}

function PublishDialog({ quiz, validation, onClose, onPublish }) {
  const [publishing, setPublishing] = useState(false);
  return (
    <ModalShell title="发布预检已通过" onClose={onClose} width={620}>
      <div style={{ padding: 22, display: "grid", gap: 16 }}>
        <div
          role="status"
          style={{
            display: "flex",
            gap: 10,
            padding: 14,
            background: "#e6f7ed",
            color: "#18794e",
            borderRadius: 10,
          }}
        >
          <Check size={20} />
          <div>
            <strong>{quiz.title}</strong>
            <div style={{ fontSize: 12, marginTop: 4 }}>
              服务端题库与分值检查通过
            </div>
          </div>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2,1fr)",
            gap: 10,
          }}
        >
          {[
            ["选择题题池", `${validation.choice_pool_count || 0} 道可用`],
            ["实际抽取", `${validation.choice_question_count || 0} 道`],
            ["编程题", `${validation.programming_question_count || 0} 道`],
            ["总分", `${validation.total_points || quiz.total_points} 分`],
            [
              "发布范围",
              `${validation.audience_count || quiz.audience?.length || 0} 条规则`,
            ],
            ["限时", `${quiz.time_limit} 分钟`],
          ].map(([label, value]) => (
            <div
              key={label}
              style={{ padding: 12, background: "#f5f6fb", borderRadius: 9 }}
            >
              <small style={{ color: "#7a8190" }}>{label}</small>
              <strong style={{ display: "block" }}>{value}</strong>
            </div>
          ))}
        </div>
        <div
          style={{
            padding: 12,
            borderRadius: 9,
            background: "#fff4dc",
            color: "#8a5a00",
            fontSize: 13,
          }}
        >
          <LockKeyhole
            size={15}
            style={{ verticalAlign: "middle", marginRight: 6 }}
          />
          发布后题目与分值将被冻结，学生立即可见。
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button type="button" onClick={onClose} style={secondary}>
            返回检查
          </button>
          <button
            type="button"
            disabled={publishing}
            onClick={async () => {
              setPublishing(true);
              try {
                await onPublish();
              } finally {
                setPublishing(false);
              }
            }}
            style={primary}
          >
            {publishing ? "发布中…" : "确认发布"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

function AudienceDialog({ currentUser, quiz, onClose, onSaved }) {
  const initial = audienceState(quiz.audience);
  const [mode, setMode] = useState(initial.mode);
  const [selected, setSelected] = useState(initial.classes);
  const [classes, setClasses] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    getProblemClassOptions(quiz.content_grade)
      .then((data) => setClasses(data.classes || []))
      .catch((reason) => setError(reason.message));
  }, [quiz.content_grade]);
  const save = async () => {
    if (mode === "classes" && !selected.length) {
      setError("请至少选择一个班级");
      return;
    }
    setSaving(true);
    setError("");
    try {
      onSaved(
        await updateAIQuizAudience(
          quiz.id,
          quiz.management_version,
          audienceFrom(mode, quiz.content_grade, selected),
        ),
      );
    } catch (reason) {
      setError(reason.message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <ModalShell title="调整小测可见范围" onClose={onClose} width={640}>
      <div style={{ padding: 22, display: "grid", gap: 18 }}>
        {error && <Notice value={{ type: "error", text: error }} />}
        <p style={{ margin: 0 }}>
          <strong>{quiz.title}</strong> · {quiz.content_grade}
        </p>
        <AudienceFields
          currentUser={currentUser}
          grade={quiz.content_grade}
          mode={mode}
          classes={selected}
          classOptions={classes}
          onMode={setMode}
          onClasses={setSelected}
        />
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button onClick={onClose} style={secondary}>
            取消
          </button>
          <button disabled={saving} onClick={save} style={primary}>
            {saving ? "保存中…" : "保存范围"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

export default function AIQuizzesTab({ currentUser }) {
  const allowedGrades = currentUser?.is_superuser
    ? GRADES
    : [currentUser?.managed_grade || GRADES[0]];
  const [filters, setFilters] = useState({
    grade: "",
    class_num: "",
    status: "",
    q: "",
    include_archived: false,
  });
  const [quizzes, setQuizzes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wizard, setWizard] = useState(null);
  const [publishState, setPublishState] = useState(null);
  const [audienceQuiz, setAudienceQuiz] = useState(null);
  const [notice, setNotice] = useState({ type: "", text: "" });
  const load = async () => {
    try {
      setQuizzes(await getAIQuizzes(filters));
    } catch (reason) {
      setNotice({ type: "error", text: reason.message });
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    let alive = true;
    getAIQuizzes(filters)
      .then((data) => alive && setQuizzes(data))
      .catch(
        (reason) => alive && setNotice({ type: "error", text: reason.message }),
      )
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [filters, setLoading, setNotice, setQuizzes]);
  const change = (key, value) => {
    setLoading(true);
    setFilters((current) => ({ ...current, [key]: value }));
  };
  const refresh = () => {
    setLoading(true);
    load();
  };
  const action = async (quiz, type) => {
    const labels = {
      close: "关闭",
      reopen: "重新开放",
      copy: "复制",
      delete: "删除",
    };
    if (type === "delete" && !window.confirm(
      `确定永久删除「${quiz.title}」吗？该小测的所有学生作答、成绩和编程提交记录也会一起删除，且无法恢复。`,
    )) return;
    if (type !== "copy" && type !== "delete" && !window.confirm(`确定${labels[type]}「${quiz.title}」吗？`)) return;
    try {
      if (type === "close") await closeAIQuiz(quiz.id, quiz.management_version);
      if (type === "reopen")
        await reopenAIQuiz(quiz.id, quiz.management_version);
      if (type === "copy") await copyAIQuiz(quiz.id);
      if (type === "delete")
        await deleteAIQuiz(quiz.id, quiz.management_version);
      setNotice({ type: "success", text: `小测已${labels[type]}` });
      await load();
    } catch (reason) {
      setNotice({ type: "error", text: reason.message });
    }
  };
  const preflight = async (quiz) => {
    setNotice({ type: "", text: "" });
    try {
      setPublishState({
        quiz,
        validation: await validateAIQuiz(quiz.id, quiz.management_version),
      });
    } catch (reason) {
      setNotice({ type: "error", text: `发布预检未通过：${reason.message}` });
    }
  };
  const published = async () => {
    try {
      await publishAIQuiz(
        publishState.quiz.id,
        publishState.quiz.management_version,
      );
      setPublishState(null);
      setNotice({ type: "success", text: "小测已发布，学生现在可以看到。" });
      await load();
    } catch (reason) {
      setPublishState(null);
      setNotice({ type: "error", text: reason.message });
    }
  };

  return (
    <section
      aria-labelledby="quiz-management-title"
      style={{ display: "grid", gap: 16 }}
    >
      <div
        style={{
          ...panel,
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <ClipboardList size={18} color="#667eea" />
        <h2 id="quiz-management-title" style={{ margin: 0, fontSize: 16 }}>
          AI 小测管理
        </h2>
        <span style={{ color: "#7a8190", fontSize: 12 }}>
          共 {quizzes.length} 份
        </span>
        <button
          type="button"
          onClick={refresh}
          aria-label="刷新小测"
          style={{ ...secondary, marginLeft: "auto", padding: 8 }}
        >
          <RefreshCw size={15} />
        </button>
        <button type="button" onClick={() => setWizard({})} style={primary}>
          <Plus size={15} />
          新建小测
        </button>
      </div>
      <Notice value={notice} />
      <div
        style={{
          ...panel,
          padding: 14,
          display: "flex",
          gap: 9,
          flexWrap: "wrap",
        }}
      >
        <select
          aria-label="小测年级筛选"
          value={filters.grade}
          onChange={(event) => change("grade", event.target.value)}
          style={input}
        >
          <option value="">全部年级</option>
          {allowedGrades.map((grade) => (
            <option key={grade}>{grade}</option>
          ))}
        </select>
        <select
          aria-label="小测班级筛选"
          value={filters.class_num}
          onChange={(event) => change("class_num", event.target.value)}
          style={input}
        >
          <option value="">全部班级</option>
          {Array.from({ length: 20 }, (_, index) => (
            <option key={index + 1} value={index + 1}>
              {index + 1}班
            </option>
          ))}
        </select>
        <select
          aria-label="小测状态筛选"
          value={filters.status}
          onChange={(event) => change("status", event.target.value)}
          style={input}
        >
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="open">进行中</option>
          <option value="closed">已关闭</option>
        </select>
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            flex: 1,
            minWidth: 220,
          }}
        >
          <Search size={15} />
          <input
            aria-label="搜索小测"
            value={filters.q}
            onChange={(event) => change("q", event.target.value)}
            placeholder="搜索小测名称"
            style={{ ...input, flex: 1 }}
          />
        </label>
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
            color: "#596172",
          }}
        >
          <input
            type="checkbox"
            checked={filters.include_archived}
            onChange={(event) =>
              change("include_archived", event.target.checked)
            }
          />
          显示已归档
        </label>
      </div>
      <div style={{ ...panel, overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 55, textAlign: "center", color: "#7a8190" }}>
            正在加载小测…
          </div>
        ) : quizzes.length === 0 ? (
          <div style={{ padding: 55, textAlign: "center", color: "#7a8190" }}>
            <ClipboardList
              size={38}
              style={{ opacity: 0.28, marginBottom: 10 }}
            />
            <p style={{ margin: 0 }}>暂无小测，可从草稿开始自由组卷。</p>
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12, padding: 18 }}>
            {quizzes.map((quiz) => {
              const state = STATUS[quiz.status] || STATUS.draft;
              return (
                <article
                  key={quiz.id}
                  style={{
                    border: "1px solid #e2e6ee",
                    borderRadius: 12,
                    padding: 15,
                    opacity: quiz.archived_at ? 0.62 : 1,
                    display: "grid",
                    gridTemplateColumns:
                      "minmax(250px,1.4fr) repeat(4,minmax(80px,.5fr)) auto",
                    alignItems: "center",
                    gap: 14,
                  }}
                >
                  <div>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 8 }}
                    >
                      <strong>{quiz.title}</strong>
                      <span
                        style={{
                          padding: "3px 8px",
                          borderRadius: 8,
                          background: state.bg,
                          color: state.color,
                          fontSize: 11,
                          fontWeight: 750,
                        }}
                      >
                        {quiz.archived_at ? "已归档" : state.label}
                      </span>
                      {quiz.content_locked && (
                        <LockKeyhole size={13} color="#7a8190" />
                      )}
                    </div>
                    <div
                      style={{ color: "#7a8190", fontSize: 11, marginTop: 5 }}
                    >
                      {quiz.content_grade} · 版本 {quiz.management_version} ·{" "}
                      {quiz.audience?.length || 0} 条发布范围
                    </div>
                  </div>
                  {[
                    ["题目", `${quiz.total_question_count} 题`],
                    [
                      "选择题",
                      `${quiz.choice_question_count} / ${quiz.choice_points} 分`,
                    ],
                    [
                      "编程题",
                      `${quiz.programming_items?.length || 0} / ${quiz.programming_points} 分`,
                    ],
                    ["时长", `${quiz.time_limit} 分钟`],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <small style={{ color: "#8a909d" }}>{label}</small>
                      <strong
                        style={{ display: "block", marginTop: 3, fontSize: 13 }}
                      >
                        {value}
                      </strong>
                    </div>
                  ))}
                  <div
                    style={{
                      display: "flex",
                      gap: 6,
                      justifyContent: "flex-end",
                      flexWrap: "wrap",
                    }}
                  >
                    {!quiz.archived_at && quiz.status === "draft" && (
                      <>
                        <button
                          aria-label={`编辑${quiz.title}`}
                          onClick={() => setWizard(quiz)}
                          title="编辑草稿"
                          style={{ ...secondary, padding: 7 }}
                        >
                          <Edit2 size={15} />
                        </button>
                        <button
                          onClick={() => preflight(quiz)}
                          style={{ ...primary, padding: "7px 10px" }}
                        >
                          <ClipboardCheck size={14} />
                          预检发布
                        </button>
                      </>
                    )}
                    {!quiz.archived_at && quiz.status !== "draft" && (
                      <button
                        onClick={() => setAudienceQuiz(quiz)}
                        style={{ ...secondary, padding: "7px 10px" }}
                      >
                        <Settings2 size={14} />
                        范围
                      </button>
                    )}
                    {!quiz.archived_at && quiz.status === "open" && (
                      <button
                        onClick={() => action(quiz, "close")}
                        style={{
                          ...secondary,
                          padding: "7px 10px",
                          color: "#a15c00",
                        }}
                      >
                        <Eye size={14} />
                        关闭
                      </button>
                    )}
                    {!quiz.archived_at && quiz.status === "closed" && (
                      <button
                        onClick={() => action(quiz, "reopen")}
                        style={{
                          ...secondary,
                          padding: "7px 10px",
                          color: "#18794e",
                        }}
                      >
                        <RotateCcw size={14} />
                        重开
                      </button>
                    )}
                    <button
                      aria-label={`复制${quiz.title}`}
                      onClick={() => action(quiz, "copy")}
                      title="复制为新草稿"
                      style={{ ...secondary, padding: 7 }}
                    >
                      <Copy size={15} />
                    </button>
                    <button
                      aria-label={`删除${quiz.title}`}
                      onClick={() => action(quiz, "delete")}
                      title="永久删除小测及相关成绩"
                      style={{ ...secondary, padding: 7, color: "#b3313d" }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
      <div
        style={{
          ...panel,
          padding: 14,
          color: "#596172",
          fontSize: 12,
          display: "flex",
          gap: 8,
        }}
      >
        <CircleAlert size={16} color="#667eea" />
        发布后组卷内容将冻结；要调整题目时，请复制为新草稿。关闭后可使用原蓝图重新开放。
      </div>
      {wizard && (
        <QuizWizard
          currentUser={currentUser}
          quiz={wizard.id ? wizard : null}
          onClose={() => setWizard(null)}
          onSaved={async (saved) => {
            setWizard(null);
            setNotice({
              type: "success",
              text: `草稿「${saved.title}」已保存`,
            });
            await load();
          }}
        />
      )}
      {publishState && (
        <PublishDialog
          {...publishState}
          onClose={() => setPublishState(null)}
          onPublish={published}
        />
      )}
      {audienceQuiz && (
        <AudienceDialog
          currentUser={currentUser}
          quiz={audienceQuiz}
          onClose={() => setAudienceQuiz(null)}
          onSaved={(saved) => {
            setAudienceQuiz(null);
            setNotice({ type: "success", text: "小测可见范围已更新" });
            setQuizzes((current) =>
              current.map((item) => (item.id === saved.id ? saved : item)),
            );
          }}
        />
      )}
    </section>
  );
}
