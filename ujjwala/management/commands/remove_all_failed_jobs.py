import django_rq
from django.core.management import BaseCommand
from django_rq import get_queue
from rq.registry import FailedJobRegistry


class Command(BaseCommand):

    def handle(self, *args, **options):
        queue = get_queue()
        failed_registry = FailedJobRegistry(queue=queue)
        jobs_id = failed_registry.get_job_ids()
        for job_id in jobs_id:
            job = queue.fetch_job(job_id)
            if job.is_failed:
                job.delete()