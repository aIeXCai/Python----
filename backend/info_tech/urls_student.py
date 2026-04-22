"""学生端路由 /api/info/"""
from django.urls import path
from .views_student import (
    QuizListView, QuizDetailView,
    QuizSubmitView, QuizResultView,
)

urlpatterns = [
    path('quizzes/', QuizListView.as_view(), name='info-quiz-list'),
    path('quizzes/<int:pk>/', QuizDetailView.as_view(), name='info-quiz-detail'),
    path('quizzes/<int:pk>/submit/', QuizSubmitView.as_view(), name='info-quiz-submit'),
    path('quizzes/<int:pk>/result/', QuizResultView.as_view(), name='info-quiz-result'),
]
