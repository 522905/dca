from django.core.management import BaseCommand

from connection_app.management.commands.compress_docs import compress_connection_app_minio_docs


class Command(BaseCommand):
	def handle(self, *args, **options):
		compress_connection_app_minio_docs()
