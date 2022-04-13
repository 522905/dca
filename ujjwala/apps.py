from django.apps import AppConfig

from django_fsm import post_transition

from ujjwala.notification import ujjwala_application_completed_event_notification


class UjjwalaAppConfig(AppConfig):
	default_auto_field = 'django.db.models.BigAutoField'
	name = 'ujjwala'

	def ready(self):
		post_transition.connect(
			ujjwala_application_completed_event_notification,
			dispatch_uid='ujjwala_application_completed_event_notification'
		)

