from django.apps import AppConfig
from django_fsm import post_transition
from material.frontend.apps import ModuleMixin

from connection_app.notification import application_completed_event_notification


class ConnectionAppConfig(ModuleMixin, AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'connection_app'
    verbose_name = 'Connection'

    def ready(self):
        post_transition.connect(
            application_completed_event_notification,
            dispatch_uid='domestic_application_completed_event_notification'
        )
