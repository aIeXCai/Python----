from django.conf import settings
from django.db.models import Max
from rest_framework.views import APIView

from users.permissions import IsStudent
from users.views import no_store_response

from .models import Language, TypingPointSubmission


class StudentBestScoresView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        scores = TypingPointSubmission.objects.filter(
            attempt__student=request.user,
            attempt__activity__is_trial=not settings.IS_PRODUCTION,
        ).values('attempt__language').annotate(best=Max('score'))

        bests = dict.fromkeys(Language.values)
        for row in scores:
            bests[row['attempt__language']] = f"{row['best']:.1f}"
        return no_store_response(bests)
