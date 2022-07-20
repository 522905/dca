import io

import requests
from django.conf import settings
from django_rq import job
from communication_log.models import CommunicationLog
from connection_app.enums import ConnectionApplicationDocumentsEnum
from connection_app.models import ConnectionApplication, minio_client
import magic

# @job
from domestic_app.utils import get_minio_public_url
from ujjwala.models import UjjwalaV2Application
import logging


def interakt_webhook_job_processing(data):
    mid = data['data']['message']['id']
    print(data['data'])
    logging.info(data['data'])
    try:
        comm_obj = CommunicationLog.objects.get(channel='whatsapp', message_id=mid)

        _type = data.get('type')
        if _type == "message_api_sent":
            comm_obj.status = "SENT"
        elif _type == "message_api_delivered":
            comm_obj.status = "DELIVERED"
        elif _type == "message_api_read":
            comm_obj.status = "READ"
        elif _type == "message_api_failed":
            comm_obj.status = "FAILED"
            method_name = 'event_{}_channel_{}'.format(comm_obj.event, 'sms')
            if hasattr(comm_obj.content_object, method_name):
                method = getattr(comm_obj.content_object, method_name)
                method()

        comm_obj.save()
    except CommunicationLog.DoesNotExist:
        pass


# @job
def infobip_webhook_job_processing(data):
    # {
    #     "bulkId": "1478260834465349757",
    #     "messages": [
    #         {
    #             "to": "41793026727",
    #             "status": {
    #                 "groupId": 1,
    #                 "groupName": "PENDING",
    #                 "id": 7,
    #                 "name": "PENDING_ENROUTE",
    #                 "description": "Message sent to next instance"
    #             },
    #             "smsCount": 1,
    #             "messageId": "844acc75-e5c6-4a21-a7e3-444c412c385b"
    #         }
    #     ]
    # }
    messages = data['messages']

    for msg in messages:
        mid = msg['messageId']
        comm_obj = CommunicationLog.objects.get(message_id=mid)
        msg_status = msg['status']['groupName']
        if msg_status in ('ACCEPTED', 'PENDING'):
            comm_obj.status = "SENT"
        elif msg_status in ('UNDELIVERABLE', 'EXPIRED', 'REJECTED'):
            comm_obj.status = "FAILED"
            # Push to vicidial
            # In Next Update
        elif msg_status == 'DELIVERED':
            comm_obj.status = "DELIVERED"
        comm_obj.save()


def move_files_to_minio_processing(id):
    obj = ConnectionApplication.objects.get(id=id)
    for doc in obj.documents.all():
        if doc.link.find("tus"):
            doc_file = requests.get(doc.link)
            # Converting PDF file to Bytes IO Stream and Uploading To minio
            doc_file_bytes = io.BytesIO(doc_file.content)
            descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
            file_extension = descriptor.mime_type.split('/')[-1]

            doc_file_name = "{}_{}.{}".format(obj.consumer_id, doc.type.lower(), file_extension)

            doc_file_bytes.seek(0)

            minio_client.put_object(
                settings.MINIO_BUCKET_NAME,
                doc_file_name,
                doc_file_bytes, doc_file_bytes.getbuffer().nbytes,
                content_type=descriptor.mime_type
            )
            doc.link = get_minio_public_url(settings.MINIO_BUCKET_NAME, doc_file_name)
            doc.save()


def send_message_on_whatsapp(id):
    obj = ConnectionApplication.objects.get(id=id)
    obj.event_completed_channel_whatsapp()



