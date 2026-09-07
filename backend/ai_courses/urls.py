from django.urls import include, path
from . import views

urlpatterns = [
    # 学生端
    path('problems/', views.ProblemListView.as_view(), name='problem-list'),
    path('problems/<str:problem_id>/', views.ProblemDetailView.as_view(), name='problem-detail'),
    path('submissions/', views.SubmissionView.as_view(), name='submission'),
    path('submissions/history/', views.SubmissionHistoryView.as_view(), name='submission-history'),
    path('scores/', views.StudentScoresView.as_view(), name='student-scores'),
    path('stats/', views.StudentStatsView.as_view(), name='student-stats'),
    path('executions/', include('execution.urls_public')),

    # 老师端
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/problems/', views.AdminProblemListView.as_view(), name='admin-problem-list'),
    path('admin/problem-classes/', views.AdminProblemClassOptionsView.as_view(), name='admin-problem-classes'),
    path('admin/problems/<str:problem_id>/', views.AdminProblemDetailView.as_view(), name='admin-problem-detail'),
    path('admin/problems/<str:problem_id>/publication/', views.AdminProblemPublicationView.as_view(), name='admin-problem-publication'),
    path('admin/problems/<str:problem_id>/restore/', views.AdminProblemRestoreView.as_view(), name='admin-problem-restore'),
    path('admin/students/', views.AdminStudentListView.as_view(), name='admin-student-list'),
    path('admin/scores/', views.AdminStudentScoresView.as_view(), name='admin-scores'),

    # Code execution
    path('run_code/', views.CodeRunView.as_view(), name='run-code'),
]
