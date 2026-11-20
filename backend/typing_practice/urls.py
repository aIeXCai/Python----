from django.urls import path

from . import views
from .bests import StudentBestScoresView
from .global_settings import TeacherGlobalArticlesView, TeacherGlobalSettingsView


urlpatterns = [
    path('teacher/settings/', TeacherGlobalSettingsView.as_view()),
    path('teacher/settings/articles/', TeacherGlobalArticlesView.as_view()),
    path('teacher/classes/', views.TeacherClassesView.as_view()),
    path('teacher/articles/', views.TeacherArticlesView.as_view()),
    path('teacher/activities/', views.TeacherActivitiesView.as_view()),
    path('teacher/activities/<int:activity_id>/close/', views.TeacherCloseActivityView.as_view()),
    path('me/bests/', StudentBestScoresView.as_view()),
    path('activities/', views.StudentActivitiesView.as_view()),
    path('activities/<int:activity_id>/leaderboard/', views.StudentLeaderboardView.as_view()),
    path('attempts/<int:attempt_id>/sync/', views.StudentSyncAttemptView.as_view()),
    path('attempts/<int:attempt_id>/pause/', views.StudentAttemptControlView.as_view(), {'action': 'pause'}),
    path('attempts/<int:attempt_id>/resume/', views.StudentAttemptControlView.as_view(), {'action': 'resume'}),
    path('attempts/', views.StudentAttemptsView.as_view()),
    path('attempts/<int:attempt_id>/', views.StudentAttemptView.as_view()),
]
