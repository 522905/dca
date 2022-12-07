import io

import requests
from django.conf import settings
from communication_log.models import CommunicationLog

import magic

from domestic_app.utils import get_minio_public_url
from ujjwala.management.commands.ujjwala_file_worker import upload_compressed_file_to_tus
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
    # messages = data['messages']
    messages = data['results']
    # Needs To Be Fixed Temporary Skipped
    messages = []
    for msg in messages:
        try:
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
        except CommunicationLog.DoesNotExist:
            continue


def compress_connection_application_documents(application_id):
    """
    Compress Connection Application Documents
    Params:
        application_id: Connection Application Object Id
    """
    from connection_app.models import ConnectionApplication

    application = ConnectionApplication.objects.filter(id=application_id).first()
    if not application:
        print("No application with id {} exists".format(application_id))

    print("Application Documents Compressing".format(application_id))

    for customer_doc in application.documents.all():
        print("Customer Doc {} {}".format(customer_doc.type, customer_doc.link))
        if not customer_doc.link:
            print("No url exist for document")
            continue
        success, upload_url, file_size = upload_compressed_file_to_tus(customer_doc.link)
        if success and not customer_doc.link == upload_url:
            customer_doc.link = upload_url

        customer_doc.save()


def move_files_to_minio_processing(application_id):
    from connection_app.models import ConnectionApplication
    from connection_app.models import minio_client

    obj = ConnectionApplication.objects.get(id=application_id)
    delete_tus_url = ''
    delete_minio_file = ''
    for doc in obj.documents.all():
        if not doc.link:
            print("No url exist for document")
            continue
        if "cnapp_" in doc.link:
            print("Already processed {}".format(doc.link))
            continue

        doc_file = requests.get("{}".format(doc.link))

        if doc_file.status_code != 200:
            doc.valid_size = False
            doc.save()
            continue

        doc_file_bytes = io.BytesIO(doc_file.content)
        descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
        file_extension = descriptor.mime_type.split('/')[-1]

        if not file_extension == 'pdf':
            if not len(doc_file.content) <= 512000:
                print("File To Be Compressed: {} Original Size: {}".format(doc.link, len(doc_file.content)))
                response = requests.get("{}{}".format(settings.THUMBOR_URL_INTERNAL_WEBP_COMPRESSED, doc.link))
            else:
                print("File To Be Converted To Webp Format {}".format(doc.link))
                response = requests.get("{}{}".format(settings.THUMBOR_URL_INTERNAL_WEBP_UNCOMPRESSED, doc.link))

            if response.status_code != 200:
                raise Exception("Could not compress file: {}".format(doc.link))

            doc_file = response

            # Converting PDF file to Bytes IO Stream and Uploading To minio
            doc_file_bytes = io.BytesIO(doc_file.content)
            descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
            file_extension = descriptor.mime_type.split('/')[-1]

        if "tus." in doc.link:
            delete_tus_url = doc.link
        else:
            delete_minio_file = doc.link.split("/")[-1]

        doc_file_name = "cnapp_{}_{}.{}".format(obj.id, doc.type.lower(), file_extension)

        doc_file_bytes.seek(0)

        minio_client.put_object(
            settings.MINIO_BUCKET_NAME,
            doc_file_name,
            doc_file_bytes, doc_file_bytes.getbuffer().nbytes,
            content_type=descriptor.mime_type
        )
        doc.link = get_minio_public_url(settings.MINIO_BUCKET_NAME, doc_file_name)
        doc.valid_size = True
        doc.save()
        print("New URL {}".format(doc.link))

        if delete_tus_url:
            del_req = requests.delete(delete_tus_url, headers={"Tus-Resumable": "1.0.0"})
            delete_tus_url = ''

        if delete_minio_file:
            # Remove object.
            minio_client.remove_object(settings.MINIO_BUCKET_NAME, delete_minio_file)
            delete_minio_file = ''


def move_sv_doc_file_tus_to_minio(url, application_id, consumer_id):
    from connection_app.models import minio_client

    delete_tus_url = ''

    if "tus." in url:
        doc_file = requests.get(url)
        # Converting PDF file to Bytes IO Stream and Uploading To minio
        doc_file_bytes = io.BytesIO(doc_file.content)
        descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
        file_extension = descriptor.mime_type.split('/')[-1]

        doc_file_name = "cnapp_{}_sv_{}.{}".format(application_id, consumer_id, file_extension)

        doc_file_bytes.seek(0)

        minio_client.put_object(
            settings.MINIO_BUCKET_NAME,
            doc_file_name,
            doc_file_bytes, doc_file_bytes.getbuffer().nbytes,
            content_type=descriptor.mime_type
        )

        if delete_tus_url:
            del_req = requests.delete(delete_tus_url, headers={"Tus-Resumable": "1.0.0"})
            delete_tus_url = ''

        return get_minio_public_url(settings.MINIO_BUCKET_NAME, doc_file_name)


def send_message_on_whatsapp(id):
    from connection_app.models import ConnectionApplication

    obj = ConnectionApplication.objects.get(id=id)
    obj.event_completed_channel_whatsapp()
