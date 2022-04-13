

def ujjwala_application_completed_event_notification(sender, instance=None, target=None, **kwargs):
	from ujjwala.models import UjjwalaV2ApplicationStatus
	from ujjwala.models import UjjwalaV2Application

	if target == UjjwalaV2ApplicationStatus.COMPLETED:
		if isinstance(instance, UjjwalaV2Application):
			import django_rq

			from ujjwala.jobs import move_ujjwala_files_to_minio_processing

			result = django_rq.enqueue(move_ujjwala_files_to_minio_processing, args=(instance.id,))
			# django_rq.enqueue(
			# 	send_message_on_whatsapp,
			# 	args=(instance.id,),
			# 	depends_on=result
			# )

