from django.apps import AppConfig
from django_fsm import post_transition

from connection_app.notification import application_completed_event_notification


class ConnectionAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'connection_app'

    def ready(self):
        post_transition.connect(
            application_completed_event_notification,
            dispatch_uid='domestic_application_completed_event_notification'
        )