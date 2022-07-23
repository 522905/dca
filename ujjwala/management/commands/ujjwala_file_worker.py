import io
import os
import time
import traceback
import uuid
import datetime

import magic
import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from tusclient import client

from ujjwala.models import UjjwalaV2Application, ConnectionDisbursement, PreInspection


def get_tus_client():
    # Set Authorization headers if it is required
    # by the tus server.
    my_client = client.TusClient('https://tus.dca.arungas.com/files/')

    return my_client


tus_client = get_tus_client()


def upload_compressed_file_to_tus(file_url):
    file = requests.get("{}".format(file_url))
    print("File To Be Compressed: {} Original Size: {}".format(file_url, len(file.content)))
    if len(file.content) <= 512000:
        return False, file_url, str(round(len(file.content)/1024))

    response = requests.get("{}{}".format(settings.THUMBOR_URL_INTERNAL, file_url))
    if response.status_code != 200:
        return False, '', '-2'

    doc_file_bytes = io.BytesIO(response.content)
    descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
    file_extension = descriptor.mime_type.split('/')[-1]

    file_path = "/tmp/{}.{}".format(str(uuid.uuid4()), file_extension)
    file = open(file_path, "wb")
    file.write(response.content)
    file_size = str(round(len(response.content)/1024))
    print("Compressed Size: {}".format(round(len(response.content))))
    file.close()
    try:
        uploader = tus_client.uploader(
            file_path=file_path,
            metadata={
                "filetype": descriptor.mime_type,
                "type": descriptor.mime_type
        })
        uploader.upload()
        os.remove(file_path)
        print("New Url: {}".format(uploader.url))
        del_req = requests.delete(file_url, headers={"Tus-Resumable": "1.0.0"})
        return True, uploader.url, file_size
    except Exception as e:
        print(e)
        return False, '', '-1'


class Command(BaseCommand):

    def handle(self, *args, **options):
        # self.handle_application(*args, **options)
        # self.handle_disb(*args, **options)
        self.handle_pi(*args, **options)

    def handle_pi(self, *args, **options):
        for dc in PreInspection.objects.filter(
            updated_on__date__lt=datetime.datetime.today().date()
        ).order_by('-id'):
            print("\n\n\nProcessing Files For PreInspection : {}".format(dc.id))
            for customer_doc in dc.documents.all():
                print("PreInspection Doc {} {}".format(customer_doc.type, customer_doc.link))
                success, upload_url, file_size = upload_compressed_file_to_tus(customer_doc.link)
                customer_doc.file_size = file_size
                if success and not customer_doc.link == upload_url:
                    customer_doc.link = upload_url
                    customer_doc.compressed = True
                customer_doc.save()

    def handle_disb(self, *args, **options):
        for dc in ConnectionDisbursement.objects.filter(
            updated_on__date__lt=datetime.datetime.today().date()
        ).order_by('-id'):
            print("\n\n\nProcessing Files For disbersment : {}".format(dc.id))
            for customer_doc in dc.documents.all():
                print("Disb Doc {} {}".format(customer_doc.type, customer_doc.link))
                success, upload_url, file_size = upload_compressed_file_to_tus(customer_doc.link)
                customer_doc.file_size = file_size
                if success and not customer_doc.link == upload_url:
                    customer_doc.link = upload_url
                    customer_doc.compressed = True
                customer_doc.save()

    def handle_application(self, *args, **options):
        #5361, 4978, 4743, 3880, 3250, 2676, 1765, 1567, 1384, 673
        for application in UjjwalaV2Application.objects.filter(id__lte=5361, id__gt=4978).order_by('-id'):
            print("\n\n\nProcessing Files For : {} {}".format(application.id, application.name))
            for customer_doc in application.documents.all():
                print("Customer Doc {} {}".format(customer_doc.type, customer_doc.link))
                success, upload_url, file_size = upload_compressed_file_to_tus(customer_doc.link)
                if success and not customer_doc.link == upload_url:
                    customer_doc.link = upload_url
                    customer_doc.compressed = True

                customer_doc.file_size = file_size
                customer_doc.save()

            for family_member in application.family_members.all():
                print("UID Front {}".format(family_member.uid_front_link))
                success, upload_url, file_size = upload_compressed_file_to_tus(family_member.uid_front_link)
                if success and not family_member.uid_front_link == upload_url:
                    family_member.uid_front_link = upload_url
                    family_member.uid_front_compressed = True

                family_member.uid_front_file_size = file_size
                family_member.save()

                print("UID Back {}".format(family_member.uid_back_link))
                success, upload_url, file_size = upload_compressed_file_to_tus(family_member.uid_back_link)
                if success and not family_member.uid_back_link == upload_url:
                    family_member.uid_back_link = upload_url
                    family_member.uid_back_compressed = True

                family_member.uid_back_file_size = file_size
                family_member.save()
