import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getAIQuizzes: vi.fn(),
  overview: vi.fn(),
  students: vi.fn(),
  attempts: vi.fn(),
  items: vi.fn(),
  reset: vi.fn(),
  regrade: vi.fn(),
  practice: vi.fn(),
}));
vi.mock("../../../api/aiQuiz.js", () => ({
  getAIQuizzes: mocks.getAIQuizzes,
  getAIQuizAnalyticsOverview: mocks.overview,
  getAIQuizAnalyticsStudents: mocks.students,
  getAIQuizAnalyticsStudentAttempts: mocks.attempts,
  getAIQuizAnalyticsItems: mocks.items,
  resetAIQuizAttempt: mocks.reset,
  regradeAIQuizItem: mocks.regrade,
}));
vi.mock("../../../api/index.js", () => ({ getAdminScores: mocks.practice }));

import AIQuizStatsTab from "./AIQuizStatsTab.jsx";

const overview = {
  quiz: {
    id: 7,
    title: "AI 混合测验",
    status: "open",
    content_grade: "七年级",
  },
  participation: {
    expected: 3,
    started: 2,
    not_started: 1,
    in_progress: 1,
    settling: 0,
    submitted: 1,
    timed_out: 0,
  },
  scores: {
    average: "88.0",
    highest: "90.0",
    lowest: "88.0",
    pass_rate: "100.0",
    choice_average_rate: "100.0",
  },
};
const studentPage = {
  pagination: { page: 1, pages: 1, total: 1, page_size: 20 },
  lamp_students: [
    {
      student_id: 9,
      display_name: "张三",
      grade: "七年级",
      class_num: "1",
      student_number: "01",
      best_total_score: "90.0",
    },
  ],
  results: [
    {
      student_id: 9,
      display_name: "张三",
      username: "s1",
      grade: "七年级",
      class_num: "1",
      student_number: "01",
      status: "submitted",
      current_attempt_id: 22,
      latest_total_score: "88.0",
      best_total_score: "90.0",
      choice_score: "40.0",
      programming_score: "48.0",
      attempt_count: 2,
      can_reset: true,
    },
  ],
};
const analysis = {
  choice_items: [
    {
      source_question_id: 1,
      source_version: 2,
      text: '执行：\n```python\nprint("<ok>")\n```',
      correct_option: "A",
      response_count: 2,
      correct: 1,
      unanswered: 0,
      correct_rate: 50,
      option_counts: { A: 1, B: 1, C: 0, D: 0 },
    },
  ],
  programming_items: [
    {
      item_id: "p1",
      title: "循环统计",
      points: "60.0",
      student_count: 2,
      submitted_count: 1,
      passed_count: 1,
      average_best_score: 80,
      pass_rate: 50,
      average_submission_count: 2,
      terminal_statuses: { succeeded: 1, wrong_answer: 1 },
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mocks.getAIQuizzes.mockResolvedValue([
    { id: 7, title: "AI 混合测验", status: "open", blueprint_version: 1 },
  ]);
  mocks.overview.mockResolvedValue(overview);
  mocks.students.mockResolvedValue(studentPage);
  mocks.items.mockResolvedValue(analysis);
  mocks.attempts.mockResolvedValue({
    pagination: { page: 1, pages: 1, total: 1 },
    results: [
      {
        attempt_id: 22,
        attempt_no: 2,
        status: "submitted",
        total_score: "88.0",
        choice_score: "40.0",
        programming_score: "48.0",
        correct_count: 1,
        choice_count: 2,
        programming_items: [
          {
            item_id: "p1",
            title: "循环统计",
            best_score: null,
            submission_count: 1,
            status: "system_issue",
          },
        ],
      },
    ],
  });
  mocks.reset.mockResolvedValue({ status: "reset" });
  mocks.regrade.mockResolvedValue({ task_id: "task-1" });
  mocks.practice.mockResolvedValue({ students: [], problems: [] });
  window.prompt = vi.fn(() => "学生设备故障");
});

describe("AIQuizStatsTab Step 10", () => {
  it("默认展示组合小测概览和历史最高成绩", async () => {
    render(<AIQuizStatsTab />);
    expect(screen.getByRole("tab", { name: "组合小测" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(await screen.findByText("张三")).toBeInTheDocument();
    expect(screen.getByText("90.0 分")).toBeInTheDocument();
    expect(screen.getByText("应参与").previousSibling).toHaveTextContent("3");
  });

  it("支持年级班级筛选，并只展示指定字段和手动阈值灯阵", async () => {
    const user = userEvent.setup();
    render(<AIQuizStatsTab />);
    await screen.findByText("张三");
    await user.selectOptions(screen.getByLabelText("小测年级筛选"), "七年级");
    await user.selectOptions(screen.getByLabelText("小测班级筛选"), "1");
    await user.click(screen.getByRole("button", { name: "查询" }));
    await waitFor(() =>
      expect(mocks.students).toHaveBeenLastCalledWith(
        "7",
        expect.objectContaining({ grade: "七年级", class_num: "1" }),
      ),
    );
    expect(
      screen.getByRole("columnheader", { name: "年级" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "班级" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "学号" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "姓名" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "历史最高成绩" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: "最近成绩" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("学号 1已亮灯")).toHaveClass("active");
    await user.clear(screen.getByLabelText("亮灯阈值"));
    await user.type(screen.getByLabelText("亮灯阈值"), "95");
    expect(screen.getByLabelText("学号 1未亮灯")).not.toHaveClass("active");
    expect(screen.getByText("每 5 秒自动刷新")).toBeInTheDocument();
  });

  it("按冻结源选项展示选择题分布，并安全显示题干代码", async () => {
    const user = userEvent.setup();
    const { container } = render(<AIQuizStatsTab />);
    await screen.findByText("张三");
    await user.click(screen.getByRole("tab", { name: "题目分析" }));
    expect(await screen.findByText(/正确率 50%/)).toBeInTheDocument();
    expect(screen.getByText("循环统计")).toBeInTheDocument();
    expect(container.querySelector("pre code")).toHaveTextContent(
      'print("<ok>")',
    );
    expect(container.querySelector("ok")).toBeNull();
  });

  it("保留题库练习成绩视图", async () => {
    mocks.practice.mockResolvedValue({
      students: [
        {
          id: 18,
          username: "demo01",
          display_name: "演示学生",
          grade: "七年级",
          class_num: "1",
          student_number: "03",
          best_score: 100,
          scores: [{ problem_id: "problem1", submitted: true, score: 100 }],
        },
      ],
      problems: [{ problem_id: "problem1", title: "输入输出" }],
    });
    render(<AIQuizStatsTab />);
    fireEvent.click(screen.getByRole("tab", { name: "题库练习" }));
    expect(await screen.findByText("题库练习成绩")).toBeInTheDocument();
    expect(mocks.practice).toHaveBeenCalled();
    expect(
      screen.getByRole("complementary", { name: "满分监控学号1至50" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("学号 3已满分")).toHaveClass("active");
    expect(screen.getByText("满分人数").previousSibling).toHaveTextContent("1");
  });
});
