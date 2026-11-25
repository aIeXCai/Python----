from django.urls import path

from . import views

urlpatterns = [
    path('me/', views.MyPointsView.as_view(), name='points-me'),
    path('leaderboard/', views.PointsLeaderboardView.as_view(), name='points-leaderboard'),
    path('ledger/', views.MyPointsLedgerView.as_view(), name='points-ledger'),
    path('admin/students/', views.AdminPointsStudentsView.as_view(), name='points-admin-students'),
    path(
        'admin/students/<int:student_id>/adjust/',
        views.AdminPointsAdjustView.as_view(), name='points-admin-adjust',
    ),
    path('admin/reset/', views.AdminPointsResetView.as_view(), name='points-admin-reset'),
]
