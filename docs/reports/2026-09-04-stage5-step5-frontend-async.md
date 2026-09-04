# 阶段 5 Step 5：前端异步体验完成报告

日期：2026-09-04

## 完成内容

- 自由运行和代码提交使用 UUID v4 `Idempotency-Key`。
- 新增任务详情、本人活动任务恢复和有限轮询 API。
- 页面显示排队中、运行中、评测中和最终结果。
- 刷新页面可恢复未完成任务；离开页面会中断轮询。
- 使用任务 ID 防止迟到结果覆盖当前状态。
- 评测完成后显示得分，错题显示正确输出、学生输出和错误信息。

## 关键文件

- `frontend/src/api/index.js`
- `frontend/src/api/index.test.js`
- `frontend/src/pages/student/ai/ProblemDetail.jsx`
- `frontend/src/pages/student/ai/ProblemDetail.test.jsx`

## 自动验证

- 定向 Vitest：43/43 通过。
- 前端全量 Vitest：275 通过，2 跳过，0 失败。
- Vite 生产构建：通过。
- ESLint：0 错误；现有代码仍有警告，不阻断构建。

## 已知限制

Step 4 Runner/Docker 沙箱尚未实施，因此真实代码任务只会入队，当前没有执行者取走。本报告验证的是前端合同、状态流转和恢复行为，不代表真实沙箱已验收。
