from django.urls import path

from .views_internal import (
    ClaimTaskView,
    CompleteTaskView,
    HeartbeatTaskView,
    RunnerNodeHeartbeatView,
)


urlpatterns = [
    path('tasks/claim', ClaimTaskView.as_view(), name='runner-task-claim'),
    path('tasks/<uuid:task_id>/heartbeat', HeartbeatTaskView.as_view(), name='runner-task-heartbeat'),
    path('tasks/<uuid:task_id>/complete', CompleteTaskView.as_view(), name='runner-task-complete'),
    path('nodes/heartbeat', RunnerNodeHeartbeatView.as_view(), name='runner-node-heartbeat'),
]
