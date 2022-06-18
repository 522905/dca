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

from ujjwala.enums import UjjwalaApplicationDocumentsEnum, PreInspectionStatusEnum
from ujjwala.models import UjjwalaV2Application, UjjwalaApplicationDocuments, PreInspection, PreInspectionDocuments


class Command(BaseCommand):

    def handle(self, *args, **options):
        applications_to_migrate = UjjwalaApplicationDocuments.objects.filter(
            type=UjjwalaApplicationDocumentsEnum.MAIN_GATE
        )

        for doc in applications_to_migrate:
            application = doc.parent
            pre_inspection_obj = PreInspection.objects.create(
                parent_id=application.id,
                latitude=application.latitude,
                longitude=application.longitude,
                accuracy=application.accuracy,
                # witness_name=application.witness_name,
                # witness_mobile_number=application.witness_mobile_number,
                mechanic_id=1,
                submitted_on=timezone.now(),
                status=PreInspectionStatusEnum.SUBMITTED
            )
            for pre_inspection_doc in application.documents.filter(
                type__in=[
                    UjjwalaApplicationDocumentsEnum.CUSTOMER_IN_KITCHEN,
                    UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO,
                    UjjwalaApplicationDocumentsEnum.MAIN_GATE,
                    UjjwalaApplicationDocumentsEnum.MECHANIC_PHOTO,
                    UjjwalaApplicationDocumentsEnum.WITNESS_PHOTO,
                ]
            ):
                PreInspectionDocuments.objects.create(
                    type=pre_inspection_doc.type,
                    link=pre_inspection_doc.link,
                    parent_id=pre_inspection_obj.id
                )
                pre_inspection_doc.delete()
