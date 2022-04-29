from django.core.management.base import BaseCommand, CommandError

from ujjwala.enums import RoboSdmsDedeupStatusEnum
from ujjwala.models import UjjwalaV2Application


class Command(BaseCommand):

    def handle(self, *args, **options):
        rejected_applications = UjjwalaV2Application.objects.filter(
            robo_sdms_dedup=RoboSdmsDedeupStatusEnum.PROCESSED_AND_DUPLICATE
        )

        for rejected_application in rejected_applications:
            rejected_application.event_reject_channel_whatsapp()
