from django.urls import path

from . import views


urlpatterns = [
    path('teacher/classes/', views.TeacherClassesView.as_view()),
    path('teacher/articles/', views.TeacherArticlesView.as_view()),
    path('teacher/activities/', views.TeacherActivitiesView.as_view()),
    path('teacher/activities/<int:activity_id>/close/', views.TeacherCloseActivityView.as_view()),
    path('activities/', views.StudentActivitiesView.as_view()),
    path('activities/<int:activity_id>/leaderboard/', views.StudentLeaderboardView.as_view()),
    path('attempts/<int:attempt_id>/sync/', views.StudentSyncAttemptView.as_view()),
    path('attempts/', views.StudentAttemptsView.as_view()),
    path('attempts/<int:attempt_id>/', views.StudentAttemptView.as_view()),
]
