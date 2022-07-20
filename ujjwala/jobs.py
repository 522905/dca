import io

import requests
from django.conf import settings
from django_rq import job
from communication_log.models import CommunicationLog
from connection_app.enums import ConnectionApplicationDocumentsEnum
from connection_app.models import minio_client
import magic

# @job
from domestic_app.utils import get_minio_public_url
from sdms.services import IoclOmcDedup
from ujjwala.enums import RoboSdmsDedeupStatusEnum

dedup_portal = IoclOmcDedup('305948', 'Arun@305948')

# def interakt_webhook_job_processing(data):
#     mid = data['data']['message']['id']
#     comm_obj = CommunicationLog.objects.get(channel='whatsapp', message_id=mid)
#
#     _type = data.get('type')
#     if _type == "message_api_sent":
#         comm_obj.status = "SENT"
#     elif _type == "message_api_delivered":
#         comm_obj.status = "DELIVERED"
#     elif _type == "message_api_read":
#         comm_obj.status = "READ"
#     elif _type == "message_api_failed":
#         comm_obj.status = "FAILED"
#         method_name = 'event_{}_channel_{}'.format(comm_obj.event, 'sms')
#         if hasattr(comm_obj.content_object, method_name):
#             method = getattr(comm_obj.content_object, method_name)
#             method()
#
#     comm_obj.save()
#
#
# # @job
# def infobip_webhook_job_processing(data):
#     # {
#     #     "bulkId": "1478260834465349757",
#     #     "messages": [
#     #         {
#     #             "to": "41793026727",
#     #             "status": {
#     #                 "groupId": 1,
#     #                 "groupName": "PENDING",
#     #                 "id": 7,
#     #                 "name": "PENDING_ENROUTE",
#     #                 "description": "Message sent to next instance"
#     #             },
#     #             "smsCount": 1,
#     #             "messageId": "844acc75-e5c6-4a21-a7e3-444c412c385b"
#     #         }
#     #     ]
#     # }
#     messages = data['messages']
#
#     for msg in messages:
#         mid = msg['messageId']
#         comm_obj = CommunicationLog.objects.get(message_id=mid)
#         msg_status = msg['status']['groupName']
#         if msg_status in ('ACCEPTED', 'PENDING'):
#             comm_obj.status = "SENT"
#         elif msg_status in ('UNDELIVERABLE', 'EXPIRED', 'REJECTED'):
#             comm_obj.status = "FAILED"
#             # Push to vicidial
#             # In Next Update
#         elif msg_status == 'DELIVERED':
#             comm_obj.status = "DELIVERED"
#         comm_obj.save()


def move_ujjwala_files_to_minio_processing(obj):
    # obj = ConnectionApplication.objects.get(id=id)
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

#
# def send_message_on_whatsapp(id):
#     obj = ConnectionApplication.objects.get(id=id)
#     obj.event_completed_channel_whatsapp()


def do_primary_omc_dedupe_check(id):
    from ujjwala.models import UjjwalaV2Application

    application = UjjwalaV2Application.objects.filter(pk=id).first()
    omc_dedupe_check_passed = True
    iocl_investigation_required = False
    for fm in application.family_members.all():

        if fm.uid_no in ('999999999999', '666666666666'):
            continue

        resp = dedup_portal.omc_aadhar_dedup(fm.uid_no)
        print(resp)

        for omc, status in resp.items():
            if status != 'Present':
                continue
            omc_dedupe_check_passed = False

            if fm.relation == 'SELF' and omc == 'IOCL':
                iocl_investigation_required = True

            fm.uid_check_result = {
                'distributor_name': omc,
                'consumer_id': 'NotAvail-CheckWithDistributor',
                'contact_address': ''
            }
            fm.save()

    if omc_dedupe_check_passed:
        application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE
        application.event_invite_for_ekyc_channel_whatsapp()
        application.save()
    else:
        if iocl_investigation_required:
            application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.IOCL_INVESTIGATION_REQUIRED
        else:
            application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.ENRICH_REJECTION_DETAILS
    application.save()
