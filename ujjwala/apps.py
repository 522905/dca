from django.apps import AppConfig
from django_fsm import post_transition
from material.frontend.apps import ModuleMixin

from ujjwala.notification import ujjwala_application_completed_event_notification


class UjjwalaAppConfig(ModuleMixin, AppConfig):
	name = 'ujjwala'
	icon = '<i class="material-icons">flight_takeoff</i>'
	default_auto_field = 'django.db.models.BigAutoField'

	def ready(self):
		post_transition.connect(
		ujjwala_application_completed_event_notification,
			dispatch_uid='ujjwala_application_completed_event_notification'
		)
