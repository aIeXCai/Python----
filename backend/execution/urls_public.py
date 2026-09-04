from django.urls import path

from .views_public import ActiveExecutionTaskView, ExecutionTaskDetailView


urlpatterns = [
    path('active/', ActiveExecutionTaskView.as_view(), name='execution-task-active'),
    path('<uuid:task_id>/', ExecutionTaskDetailView.as_view(), name='execution-task-detail'),
]
