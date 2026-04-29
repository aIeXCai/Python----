from django.urls import path
from . import views

urlpatterns = [
    path('send/', views.ChatSendView.as_view(), name='chat-send'),
    path('sessions/', views.ChatSessionListView.as_view(), name='chat-sessions'),
    path('sessions/<int:pk>/messages/', views.ChatSessionDetailView.as_view(), name='chat-session-messages'),
    path('sessions/<int:pk>/', views.ChatSessionDetailView.as_view(), name='chat-session-delete'),
]
