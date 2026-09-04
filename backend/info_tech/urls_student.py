"""学生端路由 /api/info/"""
from django.urls import path
from .views_student import (
    QuizListView, QuizDetailView,
    QuizAttemptView, QuizAttemptAnswersView, QuizAttemptSubmitView,
    LegacyQuizSubmitView, QuizResultView,
)

urlpatterns = [
    path('quizzes/', QuizListView.as_view(), name='info-quiz-list'),
    path('quizzes/<int:pk>/', QuizDetailView.as_view(), name='info-quiz-detail'),
    path('quizzes/<int:pk>/attempt/', QuizAttemptView.as_view(), name='info-quiz-attempt'),
    path('quizzes/<int:pk>/attempt/answers/', QuizAttemptAnswersView.as_view(), name='info-quiz-attempt-answers'),
    path('quizzes/<int:pk>/attempt/submit/', QuizAttemptSubmitView.as_view(), name='info-quiz-attempt-submit'),
    path('quizzes/<int:pk>/submit/', LegacyQuizSubmitView.as_view(), name='info-quiz-submit-legacy'),
    path('quizzes/<int:pk>/result/', QuizResultView.as_view(), name='info-quiz-result'),
]
