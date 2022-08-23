import io
from functools import wraps

import django_rq
import requests
from django.conf import settings
from django.db import close_old_connections
from django_rq import job
from communication_log.models import CommunicationLog
from connection_app.enums import ConnectionApplicationDocumentsEnum
from connection_app.models import minio_client
import magic

# @job
from domestic_app.utils import get_minio_public_url
from sdms.services import IoclOmcDedup
from ujjwala.enums import RoboSdmsDedeupStatusEnum, PreInspectionStatusEnum, PreInspectionTypeEnum
from ujjwala.management.commands.ujjwala_file_worker import upload_compressed_file_to_tus
from ujjwala.ujjwala_functions import application_needs_to_be_audited

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


def ensure_db_connection(func):
    @wraps(func)
    def run(*args, **kwargs):
        close_old_connections()
        return func(*args, **kwargs)

    return run


@ensure_db_connection
def do_primary_omc_dedupe_check(id):
    from ujjwala.models import UjjwalaV2Application, PreInspection

    application = UjjwalaV2Application.objects.get(pk=id)
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
        try:
            obj, created = PreInspection.objects.get_or_create(
                parent_id=application.id,
                status=PreInspectionStatusEnum.KITCHEN_PHOTO,
                type=PreInspectionTypeEnum.SELF
            )
            # application.event_invite_for_ekyc_channel_whatsapp()
            application.event_whatsapp_pre_inspection_type_self(obj.id)
        except:
            pass
        application.save()
    else:
        if iocl_investigation_required:
            application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.IOCL_INVESTIGATION_REQUIRED
        else:
            application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.ENRICH_REJECTION_DETAILS
    application.save()


def compress_connection_disbursement_documents(parent_id):
    from ujjwala.models import ConnectionDisbursementDocuments

    docs = ConnectionDisbursementDocuments.objects.filter(parent_id=parent_id, compressed=False)
    for customer_doc in docs:
        print("Disb Doc {} {} {}".format(customer_doc.parent_id, customer_doc.type, customer_doc.link))
        success, upload_url, file_size = upload_compressed_file_to_tus(customer_doc.link)
        customer_doc.file_size = file_size
        if success and not customer_doc.link == upload_url:
            customer_doc.link = upload_url
            customer_doc.compressed = True
        customer_doc.save()


def compress_pre_inspection_documents(parent_id):
    from ujjwala.models import PreInspectionDocuments

    docs = PreInspectionDocuments.objects.filter(parent_id=parent_id, compressed=False)
    for customer_doc in docs:
        print("PreInspection Doc {} {} {}".format(customer_doc.parent_id, customer_doc.type, customer_doc.link))
        success, upload_url, file_size = upload_compressed_file_to_tus(customer_doc.link)
        customer_doc.file_size = file_size
        if success and not customer_doc.link == upload_url:
            customer_doc.link = upload_url
            customer_doc.compressed = True
        customer_doc.save()


def compress_application_documents(application_id):
    from ujjwala.models import UjjwalaV2Application

    application = UjjwalaV2Application.objects.filter(id=application_id).first()
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


def enqueue_dedupe_and_audit_jobs(application_id, data):
    dedupe_job = django_rq.enqueue("ujjwala.jobs.do_primary_omc_dedupe_check", args=(application_id,))

    django_rq.enqueue(
        move_application_for_audit,
        args=(application_id, data,),
        depends_on=dedupe_job
    )


def move_application_for_audit(application_id, data):
    from ujjwala.models import UjjwalaV2Application

    move_to_audit = application_needs_to_be_audited(data)
    if move_to_audit:
        application = UjjwalaV2Application.objects.filter(id=application_id).first()
        application.transition_audit_application(audit_points=move_to_audit)
        application.save()
