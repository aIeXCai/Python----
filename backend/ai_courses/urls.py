from django.urls import include, path
from . import views
from . import views_question_bank
from . import views_quizzes
from . import views_quiz_attempts
from . import views_quiz_execution

urlpatterns = [
    # 学生端
    path('quizzes/', views_quiz_attempts.AIQuizListView.as_view(), name='ai-quiz-list'),
    path('quizzes/<int:pk>/attempt/', views_quiz_attempts.AIQuizAttemptView.as_view(), name='ai-quiz-attempt'),
    path('quizzes/<int:pk>/attempt/answers/', views_quiz_attempts.AIQuizAttemptAnswersView.as_view(), name='ai-quiz-attempt-answers'),
    path('quizzes/<int:pk>/attempt/submit/', views_quiz_attempts.AIQuizAttemptSubmitView.as_view(), name='ai-quiz-attempt-submit'),
    path('quizzes/<int:pk>/result/', views_quiz_attempts.AIQuizResultView.as_view(), name='ai-quiz-result'),
    path('quizzes/<int:pk>/attempts/', views_quiz_attempts.AIQuizAttemptHistoryView.as_view(), name='ai-quiz-attempt-history'),
    path('quizzes/<int:pk>/attempt/items/<str:item_id>/', views_quiz_execution.AIQuizProgrammingItemView.as_view(), name='ai-quiz-programming-item'),
    path('quizzes/<int:pk>/attempt/items/<str:item_id>/run/', views_quiz_execution.AIQuizProgrammingRunView.as_view(), name='ai-quiz-programming-run'),
    path('quizzes/<int:pk>/attempt/items/<str:item_id>/submit/', views_quiz_execution.AIQuizProgrammingSubmitView.as_view(), name='ai-quiz-programming-submit'),
    path('quizzes/<int:pk>/attempt/items/<str:item_id>/executions/active/', views_quiz_execution.AIQuizProgrammingActiveExecutionView.as_view(), name='ai-quiz-programming-active-execution'),
    path('problems/', views.ProblemListView.as_view(), name='problem-list'),
    path('problems/<str:problem_id>/', views.ProblemDetailView.as_view(), name='problem-detail'),
    path('submissions/', views.SubmissionView.as_view(), name='submission'),
    path('submissions/history/', views.SubmissionHistoryView.as_view(), name='submission-history'),
    path('scores/', views.StudentScoresView.as_view(), name='student-scores'),
    path('stats/', views.StudentStatsView.as_view(), name='student-stats'),
    path('executions/', include('execution.urls_public')),

    # 老师端
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/units/', views_question_bank.AdminAIUnitListView.as_view(), name='admin-ai-unit-list'),
    path('admin/units/<int:pk>/', views_question_bank.AdminAIUnitDetailView.as_view(), name='admin-ai-unit-detail'),
    path('admin/units/<int:pk>/restore/', views_question_bank.AdminAIUnitRestoreView.as_view(), name='admin-ai-unit-restore'),
    path('admin/units/<int:pk>/permanent/', views_question_bank.AdminAIUnitPermanentDeleteView.as_view(), name='admin-ai-unit-permanent-delete'),
    path('admin/choice-questions/', views_question_bank.AdminAIChoiceQuestionListView.as_view(), name='admin-ai-choice-question-list'),
    path('admin/choice-questions/import/', views_question_bank.AdminAIChoiceQuestionImportView.as_view(), name='admin-ai-choice-question-import'),
    path('admin/choice-questions/bulk-delete/', views_question_bank.AdminAIChoiceQuestionBulkDeleteView.as_view(), name='admin-ai-choice-question-bulk-delete'),
    path('admin/choice-questions/<int:pk>/', views_question_bank.AdminAIChoiceQuestionDetailView.as_view(), name='admin-ai-choice-question-detail'),
    path('admin/choice-questions/<int:pk>/copy/', views_question_bank.AdminAIChoiceQuestionCopyView.as_view(), name='admin-ai-choice-question-copy'),
    path('admin/choice-questions/<int:pk>/restore/', views_question_bank.AdminAIChoiceQuestionRestoreView.as_view(), name='admin-ai-choice-question-restore'),
    path('admin/problems/', views.AdminProblemListView.as_view(), name='admin-problem-list'),
    path('admin/problem-classes/', views.AdminProblemClassOptionsView.as_view(), name='admin-problem-classes'),
    path('admin/problems/<str:problem_id>/', views.AdminProblemDetailView.as_view(), name='admin-problem-detail'),
    path('admin/problems/<str:problem_id>/publication/', views.AdminProblemPublicationView.as_view(), name='admin-problem-publication'),
    path('admin/problems/<str:problem_id>/restore/', views.AdminProblemRestoreView.as_view(), name='admin-problem-restore'),
    path('admin/quizzes/', views_quizzes.AdminAIQuizListView.as_view(), name='admin-ai-quiz-list'),
    path('admin/quizzes/<int:pk>/', views_quizzes.AdminAIQuizDetailView.as_view(), name='admin-ai-quiz-detail'),
    path('admin/quizzes/<int:pk>/validate/', views_quizzes.AdminAIQuizValidateView.as_view(), name='admin-ai-quiz-validate'),
    path('admin/quizzes/<int:pk>/publish/', views_quizzes.AdminAIQuizPublishView.as_view(), name='admin-ai-quiz-publish'),
    path('admin/quizzes/<int:pk>/close/', views_quizzes.AdminAIQuizCloseView.as_view(), name='admin-ai-quiz-close'),
    path('admin/quizzes/<int:pk>/reopen/', views_quizzes.AdminAIQuizReopenView.as_view(), name='admin-ai-quiz-reopen'),
    path('admin/quizzes/<int:pk>/copy/', views_quizzes.AdminAIQuizCopyView.as_view(), name='admin-ai-quiz-copy'),
    path('admin/quizzes/<int:pk>/audience/', views_quizzes.AdminAIQuizAudienceView.as_view(), name='admin-ai-quiz-audience'),
    path('admin/quizzes/<int:pk>/attempts/<int:attempt_id>/reset/', views_quizzes.AdminAIQuizAttemptResetView.as_view(), name='admin-ai-quiz-attempt-reset'),
    path('admin/quizzes/<int:pk>/attempts/<int:attempt_id>/items/<str:item_id>/regrade/', views_quizzes.AdminAIQuizItemRegradeView.as_view(), name='admin-ai-quiz-item-regrade'),
    path('admin/quizzes/<int:pk>/analytics/overview/', views_quizzes.AdminAIQuizAnalyticsOverviewView.as_view(), name='admin-ai-quiz-analytics-overview'),
    path('admin/quizzes/<int:pk>/analytics/students/', views_quizzes.AdminAIQuizAnalyticsStudentsView.as_view(), name='admin-ai-quiz-analytics-students'),
    path('admin/quizzes/<int:pk>/analytics/students/<int:student_id>/attempts/', views_quizzes.AdminAIQuizAnalyticsStudentAttemptsView.as_view(), name='admin-ai-quiz-analytics-student-attempts'),
    path('admin/quizzes/<int:pk>/analytics/items/', views_quizzes.AdminAIQuizAnalyticsItemsView.as_view(), name='admin-ai-quiz-analytics-items'),
    path('admin/students/', views.AdminStudentListView.as_view(), name='admin-student-list'),
    path('admin/scores/', views.AdminStudentScoresView.as_view(), name='admin-scores'),

    # Code execution
    path('run_code/', views.CodeRunView.as_view(), name='run-code'),
]
