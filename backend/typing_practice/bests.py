from datetime import datetime, time

from django.conf import settings
from django.db.models import Max
from django.utils import timezone
from rest_framework.views import APIView

from users.permissions import IsStudent
from users.views import no_store_response

from .activities import next_rotation_at
from .models import Language, TypingPointSubmission


class StudentBestScoresView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        scores = TypingPointSubmission.objects.filter(
            attempt__student=request.user,
            attempt__activity__is_trial=not settings.IS_PRODUCTION,
        )
        bests = dict.fromkeys(Language.values)
        if request.query_params.get('period') == 'today':
            now = timezone.now()
            start = timezone.make_aware(datetime.combine(timezone.localdate(now), time.min))
            end = next_rotation_at(now)
            scores = scores.filter(settled_at__gte=start, settled_at__lt=end)
            bests['rotation_in_ms'] = max(0, round((end - now).total_seconds() * 1000))

        for row in scores.values('attempt__language').annotate(best=Max('score')):
            bests[row['attempt__language']] = f"{row['best']:.1f}"
        return no_store_response(bests)
