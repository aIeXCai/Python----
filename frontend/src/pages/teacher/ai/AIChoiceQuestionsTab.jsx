import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Copy,
  Edit2,
  FileUp,
  HelpCircle,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";

import {
  bulkDeleteAIChoiceQuestions,
  copyAIChoiceQuestion,
  createAIChoiceQuestion,
  deleteAIChoiceQuestion,
  getAIChoiceQuestions,
  getAIUnits,
  importAIChoiceQuestions,
  updateAIChoiceQuestion,
} from "../../../api/aiQuiz.js";
import { GRADES } from "../../../constants/grades.js";
import "./AIChoiceQuestionsTab.css";

const panel = {
  background: "#fff",
  borderRadius: 14,
  boxShadow: "0 2px 8px rgba(0,0,0,.06)",
};
const difficultyLabel = { easy: "容易", medium: "中等", hard: "困难" };
const difficultyColor = { easy: "#18794e", medium: "#a15c00", hard: "#b3313d" };
const iconButton = {
  width: 32,
  height: 32,
  padding: 0,
  border: "1px solid #dfe4ee",
  borderRadius: 8,
  background: "#fff",
  display: "inline-grid",
  placeItems: "center",
  cursor: "pointer",
};

function QuestionDialog({ question, sections, onClose, onSave }) {
  const [form, setForm] = useState({
    unit: question?.unit || sections[0]?.id || "",
    difficulty: question?.difficulty || "easy",
    category: question?.category || "",
    text: question?.text || "",
    option_a: question?.option_a || "",
    option_b: question?.option_b || "",
    option_c: question?.option_c || "",
    option_d: question?.option_d || "",
    answer: question?.answer || "A",
    explanation: question?.explanation || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const set = (key, value) =>
    setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onSave({ ...form, unit: Number(form.unit) });
      onClose();
    } catch (reason) {
      setError(reason.message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <div
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(28,35,55,.52)",
        display: "grid",
        placeItems: "center",
        padding: 20,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="question-dialog-title"
        style={{
          width: "min(760px, 100%)",
          maxHeight: "calc(100vh - 40px)",
          overflowY: "auto",
          background: "#fff",
          borderRadius: 16,
          boxShadow: "0 24px 70px rgba(22,30,55,.28)",
          padding: 24,
        }}
      >
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 16 }}
        >
          <h2 id="question-dialog-title" style={{ margin: 0, fontSize: 18 }}>
            {question ? "编辑选择题" : "新建选择题"}
          </h2>
          <button
            aria-label="关闭选择题弹窗"
            onClick={onClose}
            style={{
              marginLeft: "auto",
              border: 0,
              background: "transparent",
              cursor: "pointer",
            }}
          >
            <X size={20} />
          </button>
        </div>
        {error && (
          <div
            role="alert"
            style={{
              color: "#a61b29",
              background: "#ffeaec",
              padding: 10,
              borderRadius: 8,
              marginBottom: 12,
            }}
          >
            {error}
          </div>
        )}
        <form onSubmit={submit} style={{ display: "grid", gap: 13 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1fr 1fr",
              gap: 12,
            }}
          >
            <label
              style={{ display: "grid", gap: 5, fontSize: 12, fontWeight: 700 }}
            >
              所属小节
              <select
                aria-label="选择题所属小节"
                required
                value={form.unit}
                onChange={(event) => set("unit", event.target.value)}
                style={{
                  padding: 9,
                  border: "1px solid #d9deea",
                  borderRadius: 8,
                }}
              >
                <option value="">请选择小节</option>
                {sections.map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.grade} · {section.bigName} / {section.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label
              style={{ display: "grid", gap: 5, fontSize: 12, fontWeight: 700 }}
            >
              难度
              <select
                aria-label="选择题难度"
                value={form.difficulty}
                onChange={(event) => set("difficulty", event.target.value)}
                style={{
                  padding: 9,
                  border: "1px solid #d9deea",
                  borderRadius: 8,
                }}
              >
                {Object.entries(difficultyLabel).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label
              style={{ display: "grid", gap: 5, fontSize: 12, fontWeight: 700 }}
            >
              知识点
              <input
                aria-label="选择题知识点"
                value={form.category}
                onChange={(event) => set("category", event.target.value)}
                style={{
                  padding: 9,
                  border: "1px solid #d9deea",
                  borderRadius: 8,
                }}
              />
            </label>
          </div>
          <label
            style={{ display: "grid", gap: 5, fontSize: 12, fontWeight: 700 }}
          >
            题干
            <textarea
              aria-label="选择题题干"
              required
              rows={3}
              value={form.text}
              onChange={(event) => set("text", event.target.value)}
              style={{
                padding: 10,
                border: "1px solid #d9deea",
                borderRadius: 8,
                resize: "vertical",
              }}
            />
          </label>
          <div
            style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}
          >
            {"ABCD".split("").map((letter) => (
              <label
                key={letter}
                style={{
                  display: "grid",
                  gridTemplateColumns: "24px 1fr",
                  alignItems: "center",
                  gap: 5,
                  fontSize: 12,
                  fontWeight: 800,
                }}
              >
                <span>{letter}</span>
                <input
                  aria-label={`选项${letter}`}
                  required
                  value={form[`option_${letter.toLowerCase()}`]}
                  onChange={(event) =>
                    set(`option_${letter.toLowerCase()}`, event.target.value)
                  }
                  style={{
                    padding: 9,
                    border: "1px solid #d9deea",
                    borderRadius: 8,
                  }}
                />
              </label>
            ))}
          </div>
          <label
            style={{
              display: "grid",
              gap: 5,
              fontSize: 12,
              fontWeight: 700,
              maxWidth: 180,
            }}
          >
            正确答案
            <select
              aria-label="正确答案"
              value={form.answer}
              onChange={(event) => set("answer", event.target.value)}
              style={{
                padding: 9,
                border: "1px solid #d9deea",
                borderRadius: 8,
              }}
            >
              {"ABCD".split("").map((letter) => (
                <option key={letter}>{letter}</option>
              ))}
            </select>
          </label>
          <label
            style={{ display: "grid", gap: 5, fontSize: 12, fontWeight: 700 }}
          >
            答案解析
            <textarea
              aria-label="答案解析"
              rows={3}
              value={form.explanation}
              onChange={(event) => set("explanation", event.target.value)}
              style={{
                padding: 10,
                border: "1px solid #d9deea",
                borderRadius: 8,
                resize: "vertical",
              }}
            />
          </label>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "9px 16px",
                border: "1px solid #d9deea",
                borderRadius: 8,
                background: "#fff",
              }}
            >
              取消
            </button>
            <button
              disabled={saving || !sections.length}
              type="submit"
              style={{
                padding: "9px 18px",
                border: 0,
                borderRadius: 8,
                background: "#667eea",
                color: "#fff",
                fontWeight: 700,
              }}
            >
              {saving ? "保存中…" : "保存题目"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const IMPORT_EXAMPLE = [
  {
    difficulty: "easy",
    category: "人工智能基础",
    text: "以下哪项最符合人工智能的含义？",
    options: [
      { key: "A", text: "让机器完成通常需要人类智能的任务" },
      { key: "B", text: "只提高网络速度" },
      { key: "C", text: "把文件变得更大" },
      { key: "D", text: "让电脑永不关机" },
    ],
    answer: "A",
    explanation: "人工智能关注感知、推理、学习和决策等能力。",
  },
];

function ImportDialog({ sections, onClose, onImported }) {
  const [unit, setUnit] = useState(sections[0]?.id || "");
  const [fileName, setFileName] = useState("");
  const [questions, setQuestions] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const parseFile = (file) => {
    setError("");
    setQuestions([]);
    setFileName("");
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".json")) {
      setError("请选择 .json 格式的文件");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError("JSON 文件不能超过 2MB");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(
          String(reader.result || "").replace(/^\uFEFF/, ""),
        );
        const values = Array.isArray(parsed) ? parsed : parsed?.questions;
        if (!Array.isArray(values) || !values.length) {
          throw new Error("JSON 必须是非空题目数组，或包含 questions 数组");
        }
        if (values.some((item) => !item || typeof item !== "object")) {
          throw new Error("每一道题都必须是 JSON 对象");
        }
        setQuestions(values);
        setFileName(file.name);
      } catch (reason) {
        setError("文件解析失败：" + reason.message);
      }
    };
    reader.onerror = () => setError("文件读取失败，请重新选择");
    reader.readAsText(file, "UTF-8");
  };
  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (!questions.length) {
      setError("请先上传并成功解析 JSON 文件");
      return;
    }
    setImporting(true);
    try {
      const result = await importAIChoiceQuestions({
        unit_id: Number(unit),
        questions,
      });
      onImported(result.imported);
      onClose();
    } catch (reason) {
      setError(reason.message);
    } finally {
      setImporting(false);
    }
  };
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(28,35,55,.52)",
        display: "grid",
        placeItems: "center",
        padding: 20,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-title"
        style={{
          width: "min(700px, 100%)",
          maxHeight: "calc(100vh - 40px)",
          overflowY: "auto",
          background: "#fff",
          padding: 24,
          borderRadius: 16,
        }}
      >
        <div style={{ display: "flex" }}>
          <h2 id="import-title" style={{ margin: 0, fontSize: 18 }}>
            JSON 批量导入选择题
          </h2>
          <button
            aria-label="关闭导入弹窗"
            onClick={onClose}
            style={{ marginLeft: "auto", border: 0, background: "transparent" }}
          >
            <X size={20} />
          </button>
        </div>
        <form
          onSubmit={submit}
          style={{ display: "grid", gap: 12, marginTop: 16 }}
        >
          <label
            style={{ display: "grid", gap: 5, fontSize: 12, fontWeight: 700 }}
          >
            导入到小节
            <select
              aria-label="导入目标小节"
              required
              value={unit}
              onChange={(event) => setUnit(event.target.value)}
              style={{
                padding: 9,
                border: "1px solid #d9deea",
                borderRadius: 8,
              }}
            >
              <option value="">请选择</option>
              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.grade} · {section.bigName} / {section.display_name}
                </option>
              ))}
            </select>
          </label>
          <div>
            <strong style={{ display: "block", marginBottom: 6, fontSize: 12 }}>
              上传 JSON 文件
            </strong>
            <div
              onDragEnter={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                parseFile(event.dataTransfer.files?.[0]);
              }}
              onClick={() =>
                document.getElementById("ai-choice-import-file").click()
              }
              style={{
                padding: "30px 20px",
                border: "2px dashed " + (dragging ? "#4257c9" : "#667eea"),
                borderRadius: 12,
                background: fileName ? "#f2f8f4" : "#fafbff",
                textAlign: "center",
                cursor: "pointer",
              }}
            >
              <input
                id="ai-choice-import-file"
                aria-label="选择 AI 选择题 JSON 文件"
                type="file"
                accept=".json,application/json"
                onChange={(event) => parseFile(event.target.files?.[0])}
                style={{ display: "none" }}
              />
              <FileUp size={32} color="#667eea" />
              {fileName ? (
                <>
                  <p style={{ margin: "8px 0 4px", fontWeight: 750 }}>
                    {fileName}
                  </p>
                  <p style={{ margin: 0, color: "#18794e", fontSize: 12 }}>
                    ✓ 自动解析成功，共 {questions.length} 道题
                  </p>
                  <small style={{ color: "#8a909d" }}>点击可重新选择文件</small>
                </>
              ) : (
                <>
                  <p style={{ margin: "8px 0 4px", fontWeight: 750 }}>
                    拖拽 JSON 文件到这里
                  </p>
                  <p style={{ margin: 0, color: "#7a8190", fontSize: 12 }}>
                    或点击选择文件 · 最大 2MB
                  </p>
                </>
              )}
            </div>
          </div>
          <details
            style={{
              padding: "10px 12px",
              borderRadius: 9,
              background: "#f0f4ff",
              color: "#596172",
              fontSize: 12,
            }}
          >
            <summary style={{ cursor: "pointer", fontWeight: 700 }}>
              查看 JSON 格式说明
            </summary>
            <p style={{ lineHeight: 1.7 }}>
              支持与信息科技选择题相同的 options 数组格式，也兼容
              option_a、option_b、option_c、option_d
              字段。题干和选项中的代码可使用 Markdown 行内代码或代码块。
            </p>
            <pre
              style={{
                overflowX: "auto",
                margin: 0,
                whiteSpace: "pre-wrap",
                fontSize: 11,
              }}
            >
              {JSON.stringify(IMPORT_EXAMPLE, null, 2)}
            </pre>
          </details>
          {error && (
            <div role="alert" style={{ color: "#a61b29" }}>
              {error}
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
            <button type="button" onClick={onClose}>
              取消
            </button>
            <button
              type="submit"
              disabled={!unit || !questions.length || importing}
            >
              {importing
                ? "导入中…"
                : "开始导入（" + questions.length + " 题）"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AIChoiceQuestionsTab({ currentUser }) {
  const allowedGrades = currentUser?.is_superuser
    ? GRADES
    : [currentUser?.managed_grade || GRADES[0]];
  const [filters, setFilters] = useState({
    grade: allowedGrades[0],
    big_unit: "",
    unit: "",
    difficulty: "",
    q: "",
  });
  const [units, setUnits] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(null);
  const [importOpen, setImportOpen] = useState(false);
  const [notice, setNotice] = useState({ type: "", text: "" });
  const [selectedIds, setSelectedIds] = useState(new Set());
  const sections = useMemo(
    () =>
      units
        .flatMap((root) =>
          (root.sections || []).map((section) => ({
            ...section,
            grade: root.grade,
            bigName: root.display_name,
            bigId: root.id,
          })),
        )
        .filter((section) => !section.archived_at),
    [units],
  );
  const bigUnits = units.filter((unit) => !unit.archived_at);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [unitData, questionData] = await Promise.all([
        getAIUnits({
          grade: filters.grade,
          includeArchived: false,
        }),
        getAIChoiceQuestions({ ...filters, status: "all" }),
      ]);
      setUnits(unitData);
      setQuestions(questionData);
      setSelectedIds((current) => {
        const visible = new Set(questionData.map((question) => question.id));
        return new Set([...current].filter((id) => visible.has(id)));
      });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }, [filters, setNotice]);
  useEffect(() => {
    load();
  }, [load]);
  const change = (key, value) =>
    setFilters((current) => ({
      ...current,
      [key]: value,
      ...(key === "big_unit" ? { unit: "" } : {}),
    }));

  const save = async (values) => {
    if (dialog?.id)
      await updateAIChoiceQuestion(dialog.id, {
        ...values,
        expected_version: dialog.management_version,
      });
    else await createAIChoiceQuestion(values);
    setNotice({
      type: "success",
      text: dialog?.id ? "选择题已更新" : "选择题已创建",
    });
    await load();
  };
  const remove = async (question) => {
    if (!window.confirm(`确定永久删除这道选择题吗？删除后无法恢复。`)) return;
    try {
      await deleteAIChoiceQuestion(question.id, question.management_version);
      setNotice({ type: "success", text: "选择题已删除" });
      await load();
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    }
  };
  const deletableQuestions = questions.filter((question) => question.can_edit_content);
  const allSelected = deletableQuestions.length > 0 && deletableQuestions.every((question) => selectedIds.has(question.id));
  const toggleAll = () => setSelectedIds(allSelected
    ? new Set()
    : new Set(deletableQuestions.map((question) => question.id)));
  const toggleOne = (questionId) => setSelectedIds((current) => {
    const next = new Set(current);
    if (next.has(questionId)) next.delete(questionId);
    else next.add(questionId);
    return next;
  });
  const bulkRemove = async () => {
    const selected = questions.filter((question) => selectedIds.has(question.id));
    if (!selected.length) return;
    if (!window.confirm(`确定永久删除选中的 ${selected.length} 道选择题吗？删除后无法恢复。`)) return;
    try {
      const result = await bulkDeleteAIChoiceQuestions(selected.map((question) => ({
        id: question.id,
        expected_version: question.management_version,
      })));
      setSelectedIds(new Set());
      setNotice({ type: "success", text: `已删除 ${result.deleted_count} 道选择题` });
      await load();
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    }
  };
  const copy = async (question) => {
    try {
      await copyAIChoiceQuestion(question.id, question.unit);
      setNotice({ type: "success", text: "已复制为一道新题" });
      await load();
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    }
  };

  return (
    <section
      aria-labelledby="choice-bank-title"
      style={{ display: "grid", gap: 16 }}
    >
      <div
        style={{
          ...panel,
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          gap: 9,
          flexWrap: "wrap",
        }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 34,
            height: 34,
            borderRadius: 9,
            background: "#eef1ff",
            color: "#5369d8",
            display: "grid",
            placeItems: "center",
          }}
        >
          <HelpCircle size={19} strokeWidth={2.2} />
        </span>
        <h2 id="choice-bank-title" style={{ margin: 0, fontSize: 16 }}>
          AI 选择题库
        </h2>
        <span style={{ color: "#7a8190", fontSize: 12 }}>
          当前 {questions.length} 题
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            onClick={() => setImportOpen(true)}
            disabled={!sections.length}
            style={{
              padding: "8px 13px",
              border: "1px solid #667eea",
              borderRadius: 8,
              color: "#5369d8",
              background: "#fff",
              display: "flex",
              alignItems: "center",
              gap: 6,
              cursor: "pointer",
            }}
          >
            <FileUp size={16} strokeWidth={2.2} />
            JSON 导入
          </button>
          <button
            onClick={() => setDialog({})}
            disabled={!sections.length}
            style={{
              padding: "8px 13px",
              border: 0,
              borderRadius: 8,
              color: "#fff",
              background: "#667eea",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 6,
              cursor: "pointer",
            }}
          >
            <Plus size={16} strokeWidth={2.2} />
            新建选择题
          </button>
        </div>
      </div>
      {notice.text && (
        <div
          role="status"
          style={{
            padding: 10,
            borderRadius: 8,
            background: notice.type === "error" ? "#ffeaec" : "#e6f7ed",
            color: notice.type === "error" ? "#a61b29" : "#18794e",
          }}
        >
          {notice.text}
        </div>
      )}
      {!sections.length && !loading && (
        <div
          style={{
            ...panel,
            padding: 14,
            color: "#8a5a00",
            background: "#fff8e8",
          }}
        >
          请先在“单元管理”中创建至少一个小节，才能新增或导入选择题。
        </div>
      )}
      <div
        className="ai-choice-filters"
        style={{
          ...panel,
        }}
      >
        <select
          className="ai-choice-filter-control"
          aria-label="选择题年级筛选"
          value={filters.grade}
          onChange={(event) => change("grade", event.target.value)}
        >
          {allowedGrades.map((grade) => (
            <option key={grade}>{grade}</option>
          ))}
        </select>
        <select
          className="ai-choice-filter-control"
          aria-label="选择题大单元筛选"
          value={filters.big_unit}
          onChange={(event) => change("big_unit", event.target.value)}
        >
          <option value="">全部大单元</option>
          {bigUnits.map((unit) => (
            <option key={unit.id} value={unit.id}>
              {unit.display_name}
            </option>
          ))}
        </select>
        <select
          className="ai-choice-filter-control"
          aria-label="选择题小节筛选"
          value={filters.unit}
          onChange={(event) => change("unit", event.target.value)}
        >
          <option value="">全部小节</option>
          {sections
            .filter(
              (section) =>
                !filters.big_unit ||
                String(section.bigId) === String(filters.big_unit),
            )
            .map((section) => (
              <option key={section.id} value={section.id}>
                {section.display_name}
              </option>
            ))}
        </select>
        <select
          className="ai-choice-filter-control"
          aria-label="选择题难度筛选"
          value={filters.difficulty}
          onChange={(event) => change("difficulty", event.target.value)}
        >
          <option value="">全部难度</option>
          {Object.entries(difficultyLabel).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <label
          className="ai-choice-search"
        >
          <Search size={16} color="#667085" />
          <input
            aria-label="搜索选择题"
            value={filters.q}
            onChange={(event) => change("q", event.target.value)}
            placeholder="搜索题干、知识点、选项"
          />
        </label>
      </div>
      <div style={{ ...panel, padding: "10px 14px", display: "flex", alignItems: "center", gap: 10 }}>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 7, cursor: "pointer", fontSize: 13 }}>
          <input type="checkbox" aria-label="全选当前选择题" checked={allSelected} onChange={toggleAll} />
          {allSelected ? "取消全选" : "全选"}
        </label>
        <span style={{ color: "#7a8190", fontSize: 12 }}>已选择 {selectedIds.size} 道</span>
        <button type="button" disabled={!selectedIds.size} onClick={bulkRemove} style={{ marginLeft: "auto", border: 0, borderRadius: 8, padding: "8px 12px", background: selectedIds.size ? "#c81e36" : "#d7d9df", color: "#fff", display: "inline-flex", alignItems: "center", gap: 6, cursor: selectedIds.size ? "pointer" : "not-allowed" }}>
          <Trash2 size={15} />批量删除
        </button>
      </div>
      <div style={{ ...panel, overflowX: "auto" }}>
        {loading ? (
          <div style={{ padding: 50, textAlign: "center", color: "#7a8190" }}>
            正在加载选择题…
          </div>
        ) : questions.length === 0 ? (
          <div style={{ padding: 50, textAlign: "center", color: "#7a8190" }}>
            当前筛选条件下暂无选择题。
          </div>
        ) : (
          <table
            className="ai-choice-table"
            style={{ width: "100%", minWidth: 900, borderCollapse: "collapse" }}
          >
            <colgroup>
              <col className="ai-choice-select-col" />
              <col />
              <col />
              <col />
              <col />
              <col />
              <col />
            </colgroup>
            <thead>
              <tr style={{ background: "#f4f6fb" }}>
                <th className="ai-choice-select-cell">选择</th>
                {["题干", "单元", "难度", "知识点", "答案", "操作"].map(
                  (label) => (
                    <th
                      key={label}
                      style={{
                        padding: 11,
                        textAlign: "left",
                        fontSize: 12,
                        color: "#596172",
                      }}
                    >
                      {label}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {questions.map((question) => (
                <tr
                  key={question.id}
                  style={{
                    borderTop: "1px solid #edf0f5",
                    opacity: question.effectively_archived ? 0.65 : 1,
                  }}
                >
                  <td className="ai-choice-select-cell">
                    <input type="checkbox" aria-label={`选择选择题${question.id}`} disabled={!question.can_edit_content} checked={selectedIds.has(question.id)} onChange={() => toggleOne(question.id)} />
                  </td>
                  <td style={{ padding: 12, maxWidth: 350 }}>
                    <div style={{ fontWeight: 650 }}>{question.text}</div>
                    <div
                      style={{ color: "#8a909d", fontSize: 11, marginTop: 4 }}
                    >
                      版本 {question.management_version}
                    </div>
                  </td>
                  <td style={{ padding: 12, fontSize: 12 }}>
                    {question.big_unit_name} / {question.unit_name}
                  </td>
                  <td style={{ padding: 12, minWidth: 128 }}>
                    <span
                      style={{
                        color: difficultyColor[question.difficulty],
                        fontWeight: 700,
                      }}
                    >
                      {difficultyLabel[question.difficulty]}
                    </span>
                  </td>
                  <td style={{ padding: 12 }}>{question.category || "—"}</td>
                  <td style={{ padding: 12, fontWeight: 800 }}>
                    {question.answer}
                  </td>
                  <td style={{ padding: 12 }}>
                    <div style={{ display: "flex", gap: 6 }}>
                      {!question.effectively_archived &&
                        question.can_edit_content && (
                          <button
                            aria-label={`编辑选择题${question.id}`}
                            title="编辑选择题"
                            onClick={() => setDialog(question)}
                            style={{ ...iconButton, color: "#5369d8" }}
                          >
                            <Edit2 size={16} strokeWidth={2.1} />
                          </button>
                        )}
                      {!question.effectively_archived && (
                        <button
                          aria-label={`复制选择题${question.id}`}
                          title="复制选择题"
                          onClick={() => copy(question)}
                          style={{ ...iconButton, color: "#1769aa" }}
                        >
                          <Copy size={16} strokeWidth={2.1} />
                        </button>
                      )}
                      {question.can_edit_content && (
                        <button
                          aria-label={`删除选择题${question.id}`}
                          title="永久删除选择题"
                          onClick={() => remove(question)}
                          style={{ ...iconButton, color: "#b3313d" }}
                        >
                          <Trash2 size={16} strokeWidth={2.1} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {dialog && (
        <QuestionDialog
          question={dialog.id ? dialog : null}
          sections={sections}
          onClose={() => setDialog(null)}
          onSave={save}
        />
      )}
      {importOpen && (
        <ImportDialog
          sections={sections}
          onClose={() => setImportOpen(false)}
          onImported={(count) => {
            setNotice({ type: "success", text: `成功导入 ${count} 道选择题` });
            load();
          }}
        />
      )}
    </section>
  );
}
