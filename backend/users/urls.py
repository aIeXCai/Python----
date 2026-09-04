from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('me/', views.MeView.as_view(), name='me'),
    path(
        'students/<int:user_id>/password/reveal/',
        views.PasswordRevealView.as_view(),
        name='student_password_reveal',
    ),
    path(
        'students/<int:user_id>/password/reset/',
        views.PasswordResetView.as_view(),
        name='student_password_reset',
    ),
    path('<int:user_id>/', views.UserDetailView.as_view(), name='user_detail'),
]
