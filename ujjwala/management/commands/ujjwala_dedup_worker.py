from django.core.management.base import BaseCommand

from sdms.services import IoclOmcDedup
from ujjwala.enums import RoboSdmsDedeupStatusEnum, UjjwalaV2ApplicationStatus
from ujjwala.jobs import do_primary_omc_dedupe_check_worker
from ujjwala.models import UjjwalaV2Application


class Command(BaseCommand):
	# def add_arguments(self, parser):
	# 	# Positional arguments
	# 	parser.add_argument('worker_id', type=str)

	def handle(self, *args, **options):
		dedup_portal = IoclOmcDedup('305948', 'Inder@1234')

		dedup_portal.login()

		for application in UjjwalaV2Application.objects.filter(
				robo_sdms_dedup=RoboSdmsDedeupStatusEnum.NOT_PROCESSED).exclude(
					status=UjjwalaV2ApplicationStatus.APPLICATION_REJECTED):
			try:
				print(do_primary_omc_dedupe_check_worker(application.id, dedup_portal))
			except Exception as e:
				print(str(e))
				continue
