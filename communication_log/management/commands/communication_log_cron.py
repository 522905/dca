import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from communication_log.models import CommunicationLog
from datetime import datetime, timedelta


class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            d = datetime.today() - timedelta(hours=0, minutes=30)

            communication_logs = CommunicationLog.objects.filter(
                cron_processed=False, status="SENT", updated_on__lte=d, channel="whatsapp"
            )

            for rec in communication_logs:
                method_name = 'event_{}_channel_{}'.format(rec.event, 'sms')
                if hasattr(rec.content_object, method_name):
                    method = getattr(rec.content_object, method_name)
                    method()
                rec.cron_processed = True
                rec.save()
            # Cron updating its status
            requests.get("https://hc-ping.com/90b67754-f8ed-411a-af41-c8f5ceb8dae4")
        except:
            requests.get("https://hc-ping.com/90b67754-f8ed-411a-af41-c8f5ceb8dae4/fail")
