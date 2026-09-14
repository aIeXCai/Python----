import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getAIQuizzes: vi.fn(),
  createAIQuiz: vi.fn(),
  updateAIQuiz: vi.fn(),
  deleteAIQuiz: vi.fn(),
  validateAIQuiz: vi.fn(),
  publishAIQuiz: vi.fn(),
  closeAIQuiz: vi.fn(),
  reopenAIQuiz: vi.fn(),
  copyAIQuiz: vi.fn(),
  updateAIQuizAudience: vi.fn(),
  getAIUnits: vi.fn(),
  getAIChoiceQuestions: vi.fn(),
  getAdminProblems: vi.fn(),
  getProblemClassOptions: vi.fn(),
}));

vi.mock("../../../api/aiQuiz.js", () => ({
  deleteAIQuiz: mocks.deleteAIQuiz,
  closeAIQuiz: mocks.closeAIQuiz,
  copyAIQuiz: mocks.copyAIQuiz,
  createAIQuiz: mocks.createAIQuiz,
  getAIChoiceQuestions: mocks.getAIChoiceQuestions,
  getAIQuizzes: mocks.getAIQuizzes,
  getAIUnits: mocks.getAIUnits,
  publishAIQuiz: mocks.publishAIQuiz,
  reopenAIQuiz: mocks.reopenAIQuiz,
  updateAIQuiz: mocks.updateAIQuiz,
  updateAIQuizAudience: mocks.updateAIQuizAudience,
  validateAIQuiz: mocks.validateAIQuiz,
}));
vi.mock("../../../api/index.js", () => ({
  getAdminProblems: mocks.getAdminProblems,
  getProblemClassOptions: mocks.getProblemClassOptions,
}));

import AIQuizzesTab from "./AIQuizzesTab.jsx";

const currentUser = { is_superuser: false, managed_grade: "七年级" };
const units = [
  {
    id: 1,
    grade: "七年级",
    display_name: "AI 基础",
    archived_at: null,
    sections: [{ id: 11, display_name: "机器学习入门", archived_at: null }],
  },
];
const questions = [{ id: 31, unit: 11, difficulty: "easy" }];
const problems = [
  {
    problem_id: "p1",
    title: "输出问候语",
    grade_tag: "七年级",
    unit: 11,
    unit_name: "机器学习入门",
    big_unit_name: "AI 基础",
    difficulty: "入门",
    test_count: 2,
    quiz_usable: true,
  },
  {
    problem_id: "p2",
    title: "判断数字",
    grade_tag: "七年级",
    unit: 11,
    unit_name: "机器学习入门",
    big_unit_name: "AI 基础",
    difficulty: "进阶",
    test_count: 3,
    quiz_usable: true,
  },
];
const makeQuiz = (status, id) => ({
  id,
  title: `${status}小测`,
  content_grade: "七年级",
  choice_unit_ids: [11],
  choice_question_count: 1,
  choice_difficulty_ratio: { easy: 1, medium: 0, hard: 0 },
  choice_points: "40.0",
  programming_items: [
    { problem_id: "p1", title: "输出问候语", position: 1, points: "60.0" },
  ],
  programming_points: "60.0",
  total_points: "100.0",
  total_question_count: 2,
  time_limit: 45,
  status,
  management_version: 2,
  content_locked: status !== "draft",
  audience: [
    {
      scope_type: "grade_all",
      grade: "七年级",
      class_num: "",
      is_active: true,
    },
  ],
  archived_at: null,
});

beforeEach(() => {
  vi.clearAllMocks();
  window.confirm = vi.fn(() => true);
  mocks.getAIQuizzes.mockResolvedValue([]);
  mocks.getAIUnits.mockResolvedValue(units);
  mocks.getAIChoiceQuestions.mockResolvedValue(questions);
  mocks.getAdminProblems.mockResolvedValue(problems);
  mocks.getProblemClassOptions.mockResolvedValue({
    grade: "七年级",
    classes: ["1", "2"],
  });
  mocks.createAIQuiz.mockImplementation(async (values) => ({
    ...makeQuiz("draft", 9),
    ...values,
    title: values.title,
  }));
  mocks.validateAIQuiz.mockResolvedValue({
    valid: true,
    choice_pool_count: 3,
    choice_question_count: 1,
    programming_question_count: 1,
    total_points: "100.0",
    audience_count: 1,
  });
  mocks.publishAIQuiz.mockResolvedValue(makeQuiz("open", 1));
  mocks.closeAIQuiz.mockResolvedValue(makeQuiz("closed", 2));
  mocks.reopenAIQuiz.mockResolvedValue(makeQuiz("open", 3));
  mocks.copyAIQuiz.mockResolvedValue(makeQuiz("draft", 4));
  mocks.deleteAIQuiz.mockResolvedValue({ deleted: true, attempt_count: 0 });
  mocks.updateAIQuizAudience.mockImplementation(
    async (id, version, audience) => ({
      ...makeQuiz("open", id),
      management_version: version + 1,
      audience,
    }),
  );
});

describe("AIQuizzesTab Step 8", () => {
  it("通过五步组卷器创建混合小测草稿", async () => {
    const user = userEvent.setup();
    render(<AIQuizzesTab currentUser={currentUser} />);
    await user.click(await screen.findByRole("button", { name: /新建小测/ }));
    await user.type(screen.getByLabelText("小测名称"), "单元混合小测");
    await user.click(screen.getByRole("button", { name: /下一步/ }));
    await screen.findByText("选择题小节（可多选）");
    await user.click(screen.getByText("机器学习入门"));
    await user.clear(screen.getByLabelText("选择题抽题数"));
    await user.type(screen.getByLabelText("选择题抽题数"), "1");
    await user.clear(screen.getByLabelText("容易题数"));
    await user.type(screen.getByLabelText("容易题数"), "1");
    await user.click(screen.getByRole("button", { name: /下一步/ }));
    await user.click(
      await screen.findByRole("button", { name: "加入输出问候语" }),
    );
    await user.clear(screen.getByLabelText("输出问候语分值"));
    await user.type(screen.getByLabelText("输出问候语分值"), "60");
    await user.click(screen.getByRole("button", { name: /下一步/ }));
    await user.clear(screen.getByLabelText("选择题总分"));
    await user.type(screen.getByLabelText("选择题总分"), "40");
    expect(screen.getByText("当前总分：100.0 / 100.0 分")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /下一步/ }));
    expect(
      screen.getByText("本地配置检查通过。保存草稿后，请在列表执行发布预检。"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /保存草稿/ }));
    await waitFor(() =>
      expect(mocks.createAIQuiz).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "单元混合小测",
          content_grade: "七年级",
          choice_unit_ids: [11],
          choice_question_count: 1,
          choice_points: "40.0",
          programming_items: [
            { problem_id: "p1", position: 1, points: "60.0" },
          ],
          audience: [{ scope_type: "grade_all", grade: "七年级" }],
        }),
      ),
    );
  });

  it("显示题池不足并阻止保存错误配置", async () => {
    const user = userEvent.setup();
    render(<AIQuizzesTab currentUser={currentUser} />);
    await user.click(await screen.findByRole("button", { name: /新建小测/ }));
    await user.click(screen.getByRole("button", { name: "5. 预览并保存" }));
    expect(screen.getByRole("alert")).toHaveTextContent("请填写小测名称");
    expect(screen.getByRole("button", { name: /保存草稿/ })).toBeDisabled();
  });

  it("执行服务端预检后确认发布", async () => {
    const user = userEvent.setup();
    const draft = makeQuiz("draft", 1);
    mocks.getAIQuizzes.mockResolvedValue([draft]);
    render(<AIQuizzesTab currentUser={currentUser} />);
    await user.click(await screen.findByRole("button", { name: /预检发布/ }));
    expect(
      await screen.findByRole("dialog", { name: "发布预检已通过" }),
    ).toBeInTheDocument();
    expect(screen.getByText("3 道可用")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认发布" }));
    await waitFor(() => expect(mocks.publishAIQuiz).toHaveBeenCalledWith(1, 2));
  });

  it("精确展示服务端发布预检错误", async () => {
    const user = userEvent.setup();
    mocks.getAIQuizzes.mockResolvedValue([makeQuiz("draft", 1)]);
    mocks.validateAIQuiz.mockRejectedValue(
      new Error('选择题题池不足：{"medium":{"required":2,"available":1}}'),
    );
    render(<AIQuizzesTab currentUser={currentUser} />);
    await user.click(await screen.findByRole("button", { name: /预检发布/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "发布预检未通过：选择题题池不足",
    );
  });

  it("支持关闭、重开、复制和确认删除生命周期操作", async () => {
    const user = userEvent.setup();
    mocks.getAIQuizzes.mockResolvedValue([
      makeQuiz("open", 2),
      makeQuiz("closed", 3),
      makeQuiz("draft", 1),
    ]);
    render(<AIQuizzesTab currentUser={currentUser} />);
    await user.click(await screen.findByRole("button", { name: "关闭" }));
    await user.click(screen.getByRole("button", { name: "重开" }));
    await user.click(screen.getByRole("button", { name: "复制draft小测" }));
    await user.click(screen.getByRole("button", { name: "删除draft小测" }));
    await waitFor(() => {
      expect(mocks.closeAIQuiz).toHaveBeenCalledWith(2, 2);
      expect(mocks.reopenAIQuiz).toHaveBeenCalledWith(3, 2);
      expect(mocks.copyAIQuiz).toHaveBeenCalledWith(1);
      expect(mocks.deleteAIQuiz).toHaveBeenCalledWith(1, 2);
      expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("所有学生作答、成绩和编程提交记录"));
    });
  });

  it("开放后仍可以调整到指定班级", async () => {
    const user = userEvent.setup();
    mocks.getAIQuizzes.mockResolvedValue([makeQuiz("open", 2)]);
    render(<AIQuizzesTab currentUser={currentUser} />);
    await user.click(await screen.findByRole("button", { name: "范围" }));
    const dialog = await screen.findByRole("dialog", {
      name: "调整小测可见范围",
    });
    await user.click(within(dialog).getByLabelText("指定班级"));
    await user.click(within(dialog).getByText("2班"));
    await user.click(within(dialog).getByRole("button", { name: "保存范围" }));
    await waitFor(() =>
      expect(mocks.updateAIQuizAudience).toHaveBeenCalledWith(2, 2, [
        { scope_type: "class", grade: "七年级", class_num: "2" },
      ]),
    );
  });

  it("支持按年级和班级筛选小测", async () => {
    const user = userEvent.setup();
    mocks.getAIQuizzes.mockResolvedValue([makeQuiz("open", 2)]);
    render(<AIQuizzesTab currentUser={currentUser} />);
    await screen.findByText("open小测");
    await user.selectOptions(screen.getByLabelText("小测年级筛选"), "七年级");
    await user.selectOptions(screen.getByLabelText("小测班级筛选"), "2");
    await waitFor(() =>
      expect(mocks.getAIQuizzes).toHaveBeenLastCalledWith(
        expect.objectContaining({ grade: "七年级", class_num: "2" }),
      ),
    );
  });
});
