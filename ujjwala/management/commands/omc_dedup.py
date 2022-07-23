import io
import os
import time
import traceback
import uuid

import magic
import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django_currentuser.middleware import get_current_user
from tusclient import client

from sdms.services import IoclOmcDedup
from ujjwala.enums import UjjwalaApplicationDocumentsEnum, PreInspectionStatusEnum, UjjwalaV2ApplicationStatus, \
    RoboSdmsDedeupStatusEnum
from ujjwala.forms import ApplicationRejected
from ujjwala.models import UjjwalaV2Application, UjjwalaApplicationDocuments, PreInspection, PreInspectionDocuments


class Command(BaseCommand):

    def handle(self, *args, **options):
        dedup_portal = IoclOmcDedup('305948', 'Arun@305948')
        dedup_portal.login()

        for application in UjjwalaV2Application.objects.filter(
#            id__gte=5000,
            status=UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD
        ).exclude(family_members__uid_no__in=('999999999999', '0', '1')):
            for fm in application.family_members.all():

                resp = dedup_portal.omc_aadhar_dedup(fm.uid_no)
                print(resp)

                for omc, status in resp.items():
                    if status != 'Present': continue

                    fm.uid_check_result = {
                        'distributor_name': omc,
                        'consumer_id': 'NotAvail-CheckWithDistributor',
                        'contact_address': ''
                    }

                    try:
                        form = ApplicationRejected(data={
                            'rejected_reason': 'CONNECTION_ALREADY_EXIST',
                            'description': "{} {} {} {}".format(
                                fm.relation,
                                fm.uid_check_result['distributor_name'], fm.uid_check_result['consumer_id'],
                                fm.uid_check_result['contact_address']
                            )})
                        form.is_valid()
                        application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_DUPLICATE
#                       if application.status == 'DOCUMENTS_UPLOADED':
                        application.application_rejected(**form.cleaned_data)
                        application.event_ioc_dedupe_reject_channel_whatsapp()
                        application.save()
                    except Exception as e:
                        print(e)
                        pass

                    break
