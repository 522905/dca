

def application_completed_event_notification(sender, instance=None, target=None, **kwargs):
	from connection_app.enums import ConnectionApplicationLeadStatus
	from connection_app.models import ConnectionApplication
	from communication_log.jobs import send_message_on_whatsapp
	if target == ConnectionApplicationLeadStatus.SUBMITTED:
		if isinstance(instance, ConnectionApplication):
			import django_rq

			from communication_log.jobs import move_files_to_minio_processing, compress_connection_application_documents

			# result = django_rq.enqueue(compress_connection_application_documents, args=(instance.id,))

			result = django_rq.enqueue(
				move_files_to_minio_processing,
				args=(instance.id,),
				# depends_on=result
			)

			# django_rq.enqueue(
			# 	send_message_on_whatsapp,
			# 	args=(instance.id,),
			# 	depends_on=result
			# )
	elif target == ConnectionApplicationLeadStatus.COMPLETED:
		if isinstance(instance, ConnectionApplication):
			import django_rq

			from communication_log.jobs import move_files_to_minio_processing

			result = django_rq.enqueue(move_files_to_minio_processing, args=(instance.id,))
			django_rq.enqueue(
				send_message_on_whatsapp,
				args=(instance.id,),
				depends_on=result
			)
