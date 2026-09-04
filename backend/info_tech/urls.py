from django.urls import path
from .views import (
    ClassListView, UnitListView, UnitDeleteView, UnitUpdateView,
    QuestionListView, QuestionCreateView,
    QuestionUpdateView, QuestionDeleteView,
    QuestionImportView,
    QuizSessionListView, QuizSessionCreateView,
    QuizSessionUpdateView, QuizSessionDeleteView,
    QuizSessionToggleView, QuizSessionStatusView, QuizAttemptResetView,
    QuizStatsOverviewView, QuizStatsSessionView,
    QuizStatsSessionDetailView, QuizStatsGradeView,
    QuizStatsSubmissionsView,
)

urlpatterns = [
    path('admin/info/classes/', ClassListView.as_view(), name='info-classes-list'),

    # Unit
    path('admin/info/units/', UnitListView.as_view(), name='info-units-list'),
    path('admin/info/units/<int:pk>/', UnitUpdateView.as_view(), name='info-units-update'),
    path('admin/info/units/<int:pk>/delete/', UnitDeleteView.as_view(), name='info-units-delete'),

    # Question CRUD
    path('admin/info/questions/', QuestionListView.as_view(), name='info-questions-list'),
    path('admin/info/questions/create/', QuestionCreateView.as_view(), name='info-questions-create'),
    path('admin/info/questions/<int:pk>/', QuestionUpdateView.as_view(), name='info-questions-update'),
    path('admin/info/questions/<int:pk>/delete/', QuestionDeleteView.as_view(), name='info-questions-delete'),

    # Bulk import
    path('admin/info/questions/import/', QuestionImportView.as_view(), name='info-questions-import'),

    # QuizSession CRUD
    path('admin/info/sessions/', QuizSessionListView.as_view(), name='info-sessions-list'),
    path('admin/info/sessions/create/', QuizSessionCreateView.as_view(), name='info-sessions-create'),
    path('admin/info/sessions/<int:pk>/', QuizSessionUpdateView.as_view(), name='info-sessions-update'),
    path('admin/info/sessions/<int:pk>/delete/', QuizSessionDeleteView.as_view(), name='info-sessions-delete'),
    path('admin/info/sessions/<int:pk>/toggle/', QuizSessionToggleView.as_view(), name='info-sessions-toggle'),
    path('admin/info/sessions/<int:pk>/status/', QuizSessionStatusView.as_view(), name='info-sessions-status'),
    path('admin/info/sessions/<int:pk>/students/<int:student_id>/reset/', QuizAttemptResetView.as_view(), name='info-attempt-reset'),

    # Stats
    path('admin/info/stats/overview/', QuizStatsOverviewView.as_view(), name='info-stats-overview'),
    path('admin/info/stats/submissions/', QuizStatsSubmissionsView.as_view(), name='info-stats-submissions'),
    path('admin/info/stats/sessions/', QuizStatsSessionView.as_view(), name='info-stats-sessions'),
    path('admin/info/stats/sessions/<int:pk>/', QuizStatsSessionDetailView.as_view(), name='info-stats-session-detail'),
    path('admin/info/stats/grade/<str:grade>/', QuizStatsGradeView.as_view(), name='info-stats-grade'),
]
