from django.urls import include, path
from . import views
from .question_bank import views as question_bank_views
from .quizzes import views as quiz_views
from .quizzes import views_attempts as quiz_attempt_views
from .quizzes import views_execution as quiz_execution_views

urlpatterns = [
    # 学生端
    path('quizzes/', quiz_attempt_views.AIQuizListView.as_view(), name='ai-quiz-list'),
    path('quizzes/<int:pk>/attempt/', quiz_attempt_views.AIQuizAttemptView.as_view(), name='ai-quiz-attempt'),
    path('quizzes/<int:pk>/attempt/answers/', quiz_attempt_views.AIQuizAttemptAnswersView.as_view(), name='ai-quiz-attempt-answers'),
    path('quizzes/<int:pk>/attempt/submit/', quiz_attempt_views.AIQuizAttemptSubmitView.as_view(), name='ai-quiz-attempt-submit'),
    path('quizzes/<int:pk>/result/', quiz_attempt_views.AIQuizResultView.as_view(), name='ai-quiz-result'),
    path('quizzes/<int:pk>/attempts/', quiz_attempt_views.AIQuizAttemptHistoryView.as_view(), name='ai-quiz-attempt-history'),
    path('quizzes/<int:pk>/attempt/items/<str:item_id>/', quiz_execution_views.AIQuizProgrammingItemView.as_view(), name='ai-quiz-programming-item'),
    path('quizzes/<int:pk>/attempt/items/<str:item_id>/run/', quiz_execution_views.AIQuizProgrammingRunView.as_view(), name='ai-quiz-programming-run'),
    path('quizzes/<int:pk>/attempt/items/<str:item_id>/submit/', quiz_execution_views.AIQuizProgrammingSubmitView.as_view(), name='ai-quiz-programming-submit'),
    path('quizzes/<int:pk>/attempt/items/<str:item_id>/executions/active/', quiz_execution_views.AIQuizProgrammingActiveExecutionView.as_view(), name='ai-quiz-programming-active-execution'),
    path('problems/', views.ProblemListView.as_view(), name='problem-list'),
    path('problems/<str:problem_id>/', views.ProblemDetailView.as_view(), name='problem-detail'),
    path('submissions/', views.SubmissionView.as_view(), name='submission'),
    path('submissions/history/', views.SubmissionHistoryView.as_view(), name='submission-history'),
    path('scores/', views.StudentScoresView.as_view(), name='student-scores'),
    path('stats/', views.StudentStatsView.as_view(), name='student-stats'),
    path('executions/', include('execution.urls_public')),

    # 老师端
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/units/', question_bank_views.AdminAIUnitListView.as_view(), name='admin-ai-unit-list'),
    path('admin/units/<int:pk>/', question_bank_views.AdminAIUnitDetailView.as_view(), name='admin-ai-unit-detail'),
    path('admin/units/<int:pk>/restore/', question_bank_views.AdminAIUnitRestoreView.as_view(), name='admin-ai-unit-restore'),
    path('admin/units/<int:pk>/permanent/', question_bank_views.AdminAIUnitPermanentDeleteView.as_view(), name='admin-ai-unit-permanent-delete'),
    path('admin/choice-questions/', question_bank_views.AdminAIChoiceQuestionListView.as_view(), name='admin-ai-choice-question-list'),
    path('admin/choice-questions/import/', question_bank_views.AdminAIChoiceQuestionImportView.as_view(), name='admin-ai-choice-question-import'),
    path('admin/choice-questions/bulk-delete/', question_bank_views.AdminAIChoiceQuestionBulkDeleteView.as_view(), name='admin-ai-choice-question-bulk-delete'),
    path('admin/choice-questions/<int:pk>/', question_bank_views.AdminAIChoiceQuestionDetailView.as_view(), name='admin-ai-choice-question-detail'),
    path('admin/choice-questions/<int:pk>/copy/', question_bank_views.AdminAIChoiceQuestionCopyView.as_view(), name='admin-ai-choice-question-copy'),
    path('admin/choice-questions/<int:pk>/restore/', question_bank_views.AdminAIChoiceQuestionRestoreView.as_view(), name='admin-ai-choice-question-restore'),
    path('admin/problems/', views.AdminProblemListView.as_view(), name='admin-problem-list'),
    path('admin/problem-classes/', views.AdminProblemClassOptionsView.as_view(), name='admin-problem-classes'),
    path('admin/problems/<str:problem_id>/', views.AdminProblemDetailView.as_view(), name='admin-problem-detail'),
    path('admin/problems/<str:problem_id>/publication/', views.AdminProblemPublicationView.as_view(), name='admin-problem-publication'),
    path('admin/problems/<str:problem_id>/restore/', views.AdminProblemRestoreView.as_view(), name='admin-problem-restore'),
    path('admin/quizzes/', quiz_views.AdminAIQuizListView.as_view(), name='admin-ai-quiz-list'),
    path('admin/quizzes/<int:pk>/', quiz_views.AdminAIQuizDetailView.as_view(), name='admin-ai-quiz-detail'),
    path('admin/quizzes/<int:pk>/validate/', quiz_views.AdminAIQuizValidateView.as_view(), name='admin-ai-quiz-validate'),
    path('admin/quizzes/<int:pk>/publish/', quiz_views.AdminAIQuizPublishView.as_view(), name='admin-ai-quiz-publish'),
    path('admin/quizzes/<int:pk>/close/', quiz_views.AdminAIQuizCloseView.as_view(), name='admin-ai-quiz-close'),
    path('admin/quizzes/<int:pk>/reopen/', quiz_views.AdminAIQuizReopenView.as_view(), name='admin-ai-quiz-reopen'),
    path('admin/quizzes/<int:pk>/copy/', quiz_views.AdminAIQuizCopyView.as_view(), name='admin-ai-quiz-copy'),
    path('admin/quizzes/<int:pk>/audience/', quiz_views.AdminAIQuizAudienceView.as_view(), name='admin-ai-quiz-audience'),
    path('admin/quizzes/<int:pk>/attempts/<int:attempt_id>/reset/', quiz_views.AdminAIQuizAttemptResetView.as_view(), name='admin-ai-quiz-attempt-reset'),
    path('admin/quizzes/<int:pk>/attempts/<int:attempt_id>/items/<str:item_id>/regrade/', quiz_views.AdminAIQuizItemRegradeView.as_view(), name='admin-ai-quiz-item-regrade'),
    path('admin/quizzes/<int:pk>/analytics/overview/', quiz_views.AdminAIQuizAnalyticsOverviewView.as_view(), name='admin-ai-quiz-analytics-overview'),
    path('admin/quizzes/<int:pk>/analytics/students/', quiz_views.AdminAIQuizAnalyticsStudentsView.as_view(), name='admin-ai-quiz-analytics-students'),
    path('admin/quizzes/<int:pk>/analytics/students/<int:student_id>/attempts/', quiz_views.AdminAIQuizAnalyticsStudentAttemptsView.as_view(), name='admin-ai-quiz-analytics-student-attempts'),
    path('admin/quizzes/<int:pk>/analytics/items/', quiz_views.AdminAIQuizAnalyticsItemsView.as_view(), name='admin-ai-quiz-analytics-items'),
    path('admin/students/', views.AdminStudentListView.as_view(), name='admin-student-list'),
    path('admin/scores/', views.AdminStudentScoresView.as_view(), name='admin-scores'),

    # Code execution
    path('run_code/', views.CodeRunView.as_view(), name='run-code'),
]
