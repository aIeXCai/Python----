from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        from . import checks  # noqa: F401
        from .db_signals import connect_sqlite_pragmas
        connect_sqlite_pragmas()
