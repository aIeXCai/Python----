from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsStudent

from .constants import ACTIVE_STATUSES, TASK_TYPE_GRADE
from .models import ExecutionTask
from .serializers import ActiveTaskQuerySerializer, public_task_data


class ExecutionTaskDetailView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, task_id):
        try:
            task = ExecutionTask.objects.select_related('submission').get(
                public_id=task_id,
                user=request.user,
            )
        except ExecutionTask.DoesNotExist:
            return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(public_task_data(task))


class ActiveExecutionTaskView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        serializer = ActiveTaskQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(
                {'error': '参数错误', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        values = serializer.validated_data
        tasks = ExecutionTask.objects.filter(
            user=request.user,
            task_type=values['task_type'],
            status__in=ACTIVE_STATUSES,
        )
        if values['task_type'] == TASK_TYPE_GRADE:
            tasks = tasks.filter(problem__problem_id=values['problem_id'])
        task = tasks.select_related('submission').order_by('-created_at').first()
        if task is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(public_task_data(task))
