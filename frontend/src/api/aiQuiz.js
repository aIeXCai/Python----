import { createIdempotencyKey, request } from "./index.js";

const query = (params = {}) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (
      value !== "" &&
      value !== undefined &&
      value !== null &&
      value !== false
    ) {
      search.set(key, value === true ? "1" : String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : "";
};

export const getAIUnits = (params) =>
  request(`/ai/admin/units/${query(params)}`);

export const createAIUnit = (values) =>
  request("/ai/admin/units/", {
    method: "POST",
    body: JSON.stringify(values),
  });

export const updateAIUnit = (unitId, values) =>
  request(`/ai/admin/units/${unitId}/`, {
    method: "PATCH",
    body: JSON.stringify(values),
  });

export const archiveAIUnit = (unitId) =>
  request(`/ai/admin/units/${unitId}/`, {
    method: "DELETE",
  });

export const restoreAIUnit = (unitId) =>
  request(`/ai/admin/units/${unitId}/restore/`, {
    method: "POST",
  });

export const deleteAIUnit = (unitId) =>
  request(`/ai/admin/units/${unitId}/permanent/`, {
    method: "DELETE",
  });

export const getAIChoiceQuestions = (params) =>
  request(`/ai/admin/choice-questions/${query(params)}`);

export const createAIChoiceQuestion = (values) =>
  request("/ai/admin/choice-questions/", {
    method: "POST",
    body: JSON.stringify(values),
  });

export const updateAIChoiceQuestion = (questionId, values) =>
  request(`/ai/admin/choice-questions/${questionId}/`, {
    method: "PATCH",
    body: JSON.stringify(values),
  });

export const deleteAIChoiceQuestion = (questionId, expectedVersion) =>
  request(`/ai/admin/choice-questions/${questionId}/`, {
    method: "DELETE",
    body: JSON.stringify({ expected_version: expectedVersion }),
  });

export const bulkDeleteAIChoiceQuestions = (items) =>
  request("/ai/admin/choice-questions/bulk-delete/", {
    method: "POST",
    body: JSON.stringify({ items }),
  });

export const restoreAIChoiceQuestion = (questionId, expectedVersion) =>
  request(`/ai/admin/choice-questions/${questionId}/restore/`, {
    method: "POST",
    body: JSON.stringify({ expected_version: expectedVersion }),
  });

export const copyAIChoiceQuestion = (questionId, unit) =>
  request(`/ai/admin/choice-questions/${questionId}/copy/`, {
    method: "POST",
    body: JSON.stringify(unit ? { unit } : {}),
  });

export const importAIChoiceQuestions = (values) =>
  request("/ai/admin/choice-questions/import/", {
    method: "POST",
    body: JSON.stringify(values),
  });

export const getAIQuizzes = (params) =>
  request(`/ai/admin/quizzes/${query(params)}`);

export const createAIQuiz = (values) =>
  request("/ai/admin/quizzes/", {
    method: "POST",
    body: JSON.stringify(values),
  });

export const updateAIQuiz = (quizId, values) =>
  request(`/ai/admin/quizzes/${quizId}/`, {
    method: "PATCH",
    body: JSON.stringify(values),
  });

export const deleteAIQuiz = (quizId, expectedVersion) =>
  request(`/ai/admin/quizzes/${quizId}/`, {
    method: "DELETE",
    body: JSON.stringify({ expected_version: expectedVersion }),
  });

const quizAction = (quizId, action, expectedVersion) =>
  request(`/ai/admin/quizzes/${quizId}/${action}/`, {
    method: "POST",
    body: JSON.stringify({ expected_version: expectedVersion }),
  });

export const validateAIQuiz = (quizId, expectedVersion) =>
  quizAction(quizId, "validate", expectedVersion);
export const publishAIQuiz = (quizId, expectedVersion) =>
  quizAction(quizId, "publish", expectedVersion);
export const closeAIQuiz = (quizId, expectedVersion) =>
  quizAction(quizId, "close", expectedVersion);
export const reopenAIQuiz = (quizId, expectedVersion) =>
  quizAction(quizId, "reopen", expectedVersion);

export const copyAIQuiz = (quizId, title) =>
  request(`/ai/admin/quizzes/${quizId}/copy/`, {
    method: "POST",
    body: JSON.stringify(title ? { title } : {}),
  });

export const getAIQuizAudience = (quizId) =>
  request(`/ai/admin/quizzes/${quizId}/audience/`);

export const updateAIQuizAudience = (quizId, expectedVersion, audience) =>
  request(`/ai/admin/quizzes/${quizId}/audience/`, {
    method: "PATCH",
    body: JSON.stringify({ expected_version: expectedVersion, audience }),
  });

export const getAIQuizAnalyticsOverview = (quizId) =>
  request(`/ai/admin/quizzes/${quizId}/analytics/overview/`);

export const getAIQuizAnalyticsStudents = (quizId, params) =>
  request(`/ai/admin/quizzes/${quizId}/analytics/students/${query(params)}`);

export const getAIQuizAnalyticsStudentAttempts = (quizId, studentId, params) =>
  request(
    `/ai/admin/quizzes/${quizId}/analytics/students/${studentId}/attempts/${query(params)}`,
  );

export const getAIQuizAnalyticsItems = (quizId) =>
  request(`/ai/admin/quizzes/${quizId}/analytics/items/`);

export const resetAIQuizAttempt = (quizId, attemptId, reason) =>
  request(`/ai/admin/quizzes/${quizId}/attempts/${attemptId}/reset/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });

export const regradeAIQuizItem = (
  quizId,
  attemptId,
  itemId,
  idempotencyKey = createIdempotencyKey(),
) =>
  request(
    `/ai/admin/quizzes/${quizId}/attempts/${attemptId}/items/${encodeURIComponent(itemId)}/regrade/`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
    },
  );
