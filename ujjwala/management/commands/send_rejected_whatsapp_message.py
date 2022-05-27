from django.core.management.base import BaseCommand, CommandError

from ujjwala.enums import RoboSdmsDedeupStatusEnum
from ujjwala.models import UjjwalaV2Application


class Command(BaseCommand):

    def handle(self, *args, **options):
        rejected_applications = UjjwalaV2Application.objects.filter(
            robo_sdms_dedup=RoboSdmsDedeupStatusEnum.PROCESSED_AND_DUPLICATE
        ).exclude(
            family_members__uid_check_result=None
        )

        for rejected_application in rejected_applications:
            print('{}\n'.format(str(rejected_application.pk)))
            rejected_application.event_reject_channel_whatsapp()
