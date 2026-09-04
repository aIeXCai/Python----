"""Token authentication with a configurable maximum lifetime."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication


def token_is_expired(token, now=None):
    now = now or timezone.now()
    lifetime = timedelta(hours=settings.TOKEN_TTL_HOURS)
    return now >= token.created + lifetime


def get_or_create_valid_token(user):
    model = TokenAuthentication().get_model()
    token = model.objects.filter(user=user).first()
    if token and token_is_expired(token):
        token.delete()
        token = None
    if token is None:
        token = model.objects.create(user=user)
    return token


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related('user').get(key=key)
        except model.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed('登录凭据无效。') from exc

        if not token.user.is_active:
            token.delete()
            raise exceptions.AuthenticationFailed('账号已停用。')
        if token_is_expired(token):
            token.delete()
            raise exceptions.AuthenticationFailed('登录已过期，请重新登录。')
        return token.user, token
