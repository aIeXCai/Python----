import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  bulkDeleteAIChoiceQuestions: vi.fn(),
  copyAIChoiceQuestion: vi.fn(),
  createAIChoiceQuestion: vi.fn(),
  deleteAIChoiceQuestion: vi.fn(),
  getAIChoiceQuestions: vi.fn(),
  getAIUnits: vi.fn(),
  importAIChoiceQuestions: vi.fn(),
  updateAIChoiceQuestion: vi.fn(),
}));

vi.mock("../../../api/aiQuiz.js", () => mocks);

import AIChoiceQuestionsTab from "./AIChoiceQuestionsTab.jsx";

const questions = [1, 2].map((id) => ({
  id,
  unit: 11,
  unit_name: "输入输出",
  big_unit_name: "Python 基础",
  difficulty: "easy",
  category: "基础",
  text: `选择题 ${id}`,
  answer: "A",
  management_version: 1,
  can_edit_content: true,
  effectively_archived: false,
}));

beforeEach(() => {
  vi.clearAllMocks();
  window.confirm = vi.fn(() => true);
  mocks.getAIUnits.mockResolvedValue([{
    id: 1,
    grade: "七年级",
    display_name: "Python 基础",
    archived_at: null,
    sections: [{ id: 11, display_name: "输入输出", archived_at: null }],
  }]);
  mocks.getAIChoiceQuestions.mockResolvedValue(questions);
  mocks.bulkDeleteAIChoiceQuestions.mockResolvedValue({ deleted_count: 2 });
});

describe("AIChoiceQuestionsTab batch deletion", () => {
  it("支持全选、取消全选和确认后批量永久删除", async () => {
    const user = userEvent.setup();
    render(<AIChoiceQuestionsTab currentUser={{ managed_grade: "七年级" }} />);

    const selectAll = await screen.findByLabelText("全选当前选择题");
    await user.click(selectAll);
    expect(screen.getByText("已选择 2 道")).toBeInTheDocument();
    expect(screen.getByText("取消全选")).toBeInTheDocument();
    await user.click(screen.getByText("取消全选"));
    expect(screen.getByText("已选择 0 道")).toBeInTheDocument();

    await user.click(selectAll);
    await user.click(screen.getByRole("button", { name: "批量删除" }));
    await waitFor(() => expect(mocks.bulkDeleteAIChoiceQuestions).toHaveBeenCalledWith([
      { id: 1, expected_version: 1 },
      { id: 2, expected_version: 1 },
    ]));
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("删除后无法恢复"));
  });
});
