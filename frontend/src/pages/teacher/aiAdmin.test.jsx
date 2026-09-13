import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("lucide-react", () => {
  const icon = (name) =>
    function MockIcon() {
      return <span data-testid={`icon-${name}`}>{name}</span>;
    };
  return {
    Archive: icon("archive"),
    ArrowDown: icon("down-arrow"),
    ArrowLeft: icon("back"),
    ArrowUp: icon("up-arrow"),
    BarChart3: icon("chart"),
    Check: icon("check"),
    BookOpen: icon("book"),
    Bot: icon("bot"),
    ChevronDown: icon("down"),
    ChevronLeft: icon("left"),
    Code2: icon("code"),
    Download: icon("download"),
    FileClock: icon("file-clock"),
    History: icon("history"),
    Loader: icon("loader"),
    ChevronRight: icon("right"),
    CircleAlert: icon("alert"),
    ClipboardCheck: icon("check-quiz"),
    ClipboardList: icon("quiz"),
    Copy: icon("copy"),
    Edit2: icon("edit"),
    Eye: icon("eye"),
    EyeOff: icon("eye-off"),
    FileUp: icon("file"),
    HelpCircle: icon("help"),
    Layers3: icon("layers"),
    LockKeyhole: icon("lock"),
    Plus: icon("plus"),
    RefreshCw: icon("refresh"),
    RotateCcw: icon("restore"),
    Search: icon("search"),
    Settings2: icon("settings"),
    Tag: icon("tag"),
    Trash2: icon("trash"),
    Users: icon("users"),
    X: icon("x"),
  };
});

const navigate = vi.fn();
vi.mock("react-router-dom", () => ({ useNavigate: () => navigate }));

const localStorageMock = {
  getItem: vi.fn(),
  removeItem: vi.fn(),
  setItem: vi.fn(),
};
Object.defineProperty(global, "localStorage", { value: localStorageMock });

const units = [
  {
    id: 1,
    grade: "七年级",
    name: "ai-foundation",
    display_name: "人工智能基础",
    order: 1,
    archived_at: null,
    choice_question_count: 1,
    programming_problem_count: 1,
    sections: [
      {
        id: 11,
        parent: 1,
        grade: "七年级",
        name: "concepts",
        display_name: "认识人工智能",
        order: 1,
        archived_at: null,
        choice_question_count: 1,
        programming_problem_count: 1,
      },
    ],
  },
];

const questions = [
  {
    id: 31,
    unit: 11,
    grade: "七年级",
    unit_name: "认识人工智能",
    big_unit_id: 1,
    big_unit_name: "人工智能基础",
    difficulty: "easy",
    category: "概念",
    text: "什么是人工智能？",
    option_a: "机器表现出的智能",
    option_b: "一张纸",
    option_c: "一支笔",
    option_d: "一本书",
    answer: "A",
    explanation: "A 正确",
    management_version: 2,
    archived_at: null,
    effectively_archived: false,
    can_edit_content: true,
  },
];

const problems = [
  {
    problem_id: "p001",
    title: "排序算法",
    difficulty: "入门",
    grade_tag: "七年级",
    unit: 11,
    unit_name: "认识人工智能",
    big_unit_name: "人工智能基础",
    test_count: 2,
    quiz_usable: true,
    quiz_unusable_reasons: [],
    management_version: 1,
    can_edit_content: true,
    can_archive: true,
    publishing_suspended: false,
    archived_at: null,
    publication_label: "七年级可见",
    publication: {
      all_school: false,
      scopes: [
        { grade: "七年级", visible: true, all_classes: true, classes: [] },
      ],
    },
  },
  {
    problem_id: "p002",
    title: "动态规划",
    difficulty: "进阶",
    grade_tag: "",
    unit: null,
    unit_name: "",
    big_unit_name: "",
    test_count: 2,
    quiz_usable: false,
    quiz_unusable_reasons: [
      { code: "unit_missing", label: "未归类到 AI 小节" },
    ],
    management_version: 1,
    can_edit_content: true,
    can_archive: true,
    publishing_suspended: true,
    archived_at: null,
    publication_label: "已暂停",
    publication: { all_school: false, scopes: [] },
  },
];

const scores = {
  students: [
    {
      id: 7,
      display_name: "张三",
      student_number: "01",
      grade: "七年级",
      class_num: "1",
      scores: [{ problem_id: "p001", submitted: true, score: 95 }],
    },
  ],
  problems: [{ problem_id: "p001", title: "排序算法" }],
};

const response = (data) =>
  Promise.resolve({ ok: true, status: 200, json: async () => data });

beforeEach(() => {
  vi.clearAllMocks();
  window.confirm = vi.fn(() => true);
  localStorageMock.getItem.mockImplementation((key) =>
    key === "user"
      ? JSON.stringify({
          username: "Alex",
          role: "teacher",
          is_superuser: true,
          managed_grade: "",
        })
      : "token",
  );
  global.fetch = vi.fn((url, options = {}) => {
    const method = options.method || "GET";
    if (url.includes("/ai/admin/quizzes/")) return response([]);
    if (url.includes("/choice-questions/import/"))
      return response({ imported: 1 });
    if (url.includes("/choice-questions/31/copy/"))
      return response({ ...questions[0], id: 32 });
    if (url.includes("/choice-questions/31/restore/"))
      return response(questions[0]);
    if (url.includes("/choice-questions/31/"))
      return response(
        method === "PATCH"
          ? { ...questions[0], text: "修改后的题干", management_version: 3 }
          : questions[0],
      );
    if (url.includes("/choice-questions/"))
      return response(
        method === "POST" ? { ...questions[0], id: 33 } : questions,
      );
    if (/\/ai\/admin\/units\/\d+\/restore\/$/.test(url))
      return response(units[0]);
    if (/\/ai\/admin\/units\/\d+\/$/.test(url)) return response(units[0]);
    if (url.includes("/ai/admin/units/"))
      return response(method === "POST" ? units[0] : units);
    if (url.includes("/ai/admin/problem-classes/"))
      return response({ grade: "七年级", classes: ["1"] });
    if (url.includes("/publication/"))
      return response({
        management_version: 2,
        publishing_suspended: false,
        all_school: false,
        scopes: [],
      });
    if (/\/ai\/admin\/problems\/[^/]+\/$/.test(url))
      return response(
        method === "PATCH"
          ? { ...problems[0], title: "修改后的编程题" }
          : problems[0],
      );
    if (url.includes("/ai/admin/problems/"))
      return response(
        method === "POST"
          ? { created: [], updated: [], skipped: [], failed: [] }
          : problems,
      );
    if (url.includes("/ai/admin/scores/")) return response(scores);
    return response([]);
  });
});

import AiAdmin from "./aiAdmin.jsx";

describe("AI 教师管理 Step 7", () => {
  it("提供五个可访问的一级区域并默认展示单元管理", async () => {
    render(<AiAdmin />);
    expect(screen.getAllByRole("tab")).toHaveLength(5);
    expect(screen.getByRole("tab", { name: /单元管理/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(await screen.findByText("人工智能基础")).toBeInTheDocument();
    expect(
      screen.getAllByText(/1 道选择题 · 1 道编程题/).length,
    ).toBeGreaterThan(0);
  });

  it("可以创建大单元并提交明确层级数据", async () => {
    const user = userEvent.setup();
    render(<AiAdmin />);
    await screen.findByText("人工智能基础");
    await user.click(screen.getByRole("button", { name: /新建单元/ }));
    await user.clear(screen.getByLabelText("单元显示名称"));
    await user.type(screen.getByLabelText("单元显示名称"), "生成式人工智能");
    await user.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/ai/admin/units/"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("生成式人工智能"),
        }),
      ),
    );
  });

  it("选择题库支持列表、筛选和新增题目", async () => {
    const user = userEvent.setup();
    render(<AiAdmin />);
    await user.click(screen.getByRole("tab", { name: /选择题库/ }));
    expect(await screen.findByText("什么是人工智能？")).toBeInTheDocument();
    expect(screen.getByLabelText("选择题难度筛选")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /新建选择题/ }));
    await user.type(screen.getByLabelText("选择题题干"), "新的选择题");
    for (const letter of "ABCD")
      await user.type(screen.getByLabelText(`选项${letter}`), `选项${letter}`);
    await user.click(screen.getByRole("button", { name: "保存题目" }));
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/choice-questions/"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("新的选择题"),
        }),
      ),
    );
  });

  it("选择题支持复制、删除和 JSON 导入", async () => {
    const user = userEvent.setup();
    render(<AiAdmin />);
    await user.click(screen.getByRole("tab", { name: /选择题库/ }));
    await screen.findByText("什么是人工智能？");
    await user.click(screen.getByRole("button", { name: "复制选择题31" }));
    await screen.findByText("已复制为一道新题");
    await user.click(screen.getByRole("button", { name: "删除选择题31" }));
    expect(window.confirm).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /JSON 导入/ }));
    const file = new File(
      [
        JSON.stringify([
          {
            difficulty: "medium",
            category: "代码阅读",
            text: "代码 print(1) 会输出什么？",
            options: [
              { key: "A", text: "1" },
              { key: "B", text: "0" },
              { key: "C", text: "报错" },
              { key: "D", text: "无输出" },
            ],
            answer: "A",
            explanation: "print 输出 1。",
          },
        ]),
      ],
      "ai-questions.json",
      { type: "application/json" },
    );
    await user.upload(screen.getByLabelText("选择 AI 选择题 JSON 文件"), file);
    expect(
      await screen.findByText("✓ 自动解析成功，共 1 道题"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始导入（1 题）" }));
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/choice-questions/import/"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"text":"代码 print(1) 会输出什么？"'),
        }),
      ),
    );
  });

  it("AI 选择题 JSON 文件解析失败时不会发送导入请求", async () => {
    const user = userEvent.setup();
    render(<AiAdmin />);
    await user.click(screen.getByRole("tab", { name: /选择题库/ }));
    await screen.findByText("什么是人工智能？");
    await user.click(screen.getByRole("button", { name: /JSON 导入/ }));
    await user.upload(
      screen.getByLabelText("选择 AI 选择题 JSON 文件"),
      new File(["not-json"], "broken.json", { type: "application/json" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("文件解析失败");
    expect(
      screen.getByRole("button", { name: "开始导入（0 题）" }),
    ).toBeDisabled();
    expect(
      global.fetch.mock.calls.some(([url]) =>
        String(url).includes("/choice-questions/import/"),
      ),
    ).toBe(false);
  });

  it("编程题库保留归类筛选、可组卷状态和编辑入口", async () => {
    const user = userEvent.setup();
    render(<AiAdmin />);
    await user.click(screen.getByRole("tab", { name: /编程题库/ }));
    expect(await screen.findByText("排序算法")).toBeInTheDocument();
    expect(screen.getByText("人工智能基础 / 认识人工智能")).toBeInTheDocument();
    expect(screen.getAllByText("可组卷").length).toBeGreaterThan(0);
    const gradeFilter = screen.getByLabelText("适用年级筛选");
    expect(gradeFilter.style.minHeight).toBe("36px");
    expect(gradeFilter.style.borderRadius).toBe("8px");
    const editButton = screen.getByRole("button", { name: "编辑排序算法" });
    expect(editButton.style.width).toBe("32px");
    expect(editButton.style.height).toBe("32px");
    expect(editButton.style.borderRadius).toBe("8px");
    await user.selectOptions(
      screen.getByLabelText("所属 AI 小节筛选"),
      "unclassified",
    );
    expect(screen.getByText("动态规划")).toBeInTheDocument();
    expect(screen.queryByText("排序算法")).not.toBeInTheDocument();
  });

  it("小测管理已接入自由组卷，成绩统计保留旧练习数据", async () => {
    const user = userEvent.setup();
    render(<AiAdmin />);
    await user.click(screen.getByRole("tab", { name: /小测管理/ }));
    expect(
      await screen.findByRole("heading", { name: "AI 小测管理" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /新建小测/ }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /成绩统计/ }));
    await user.click(screen.getByRole("tab", { name: "题库练习" }));
    expect(await screen.findByText("张三")).toBeInTheDocument();
    expect(screen.getByText("95")).toBeInTheDocument();
  });

  it("返回按钮导航教师首页", async () => {
    const user = userEvent.setup();
    render(<AiAdmin />);
    await user.click(screen.getByRole("button", { name: /返回主页/ }));
    expect(navigate).toHaveBeenCalledWith("/teacher/dashboard");
  });
});
