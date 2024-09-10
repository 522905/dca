import io
import json
import re
from functools import wraps

import django_rq
from django.http import  JsonResponse
import arrow, os
import requests
import track
from django.conf import settings
from django.db import close_old_connections
from google.cloud import  dialogflow_v2 as dialogflow
from communication_log.models import CommunicationLog
import tempfile
import magic
from functools import wraps
from domestic_app.utils import get_minio_public_url
# from ujjwala.jobs import ensure_db_connection
from django.db import close_old_connections
from ujjwala.management.commands.ujjwala_file_worker import upload_compressed_file_to_tus
from ujjwala.views import  WhatsappPreInspection
import logging

# Initialize logger
logger = logging.getLogger("chatbot_views")

def ensure_db_connection(func):
    @wraps(func)
    def run(*args, **kwargs):
        close_old_connections()
        return func(*args, **kwargs)
    return run


def interakt_webhook_job_processing(data):
    if data["type"] == "Webhook Test":
        return JsonResponse({'status': 'success'}, status=200)
    mid = data['data']['message']['id']
    print(data['data'])
    logging.info(data['data'])
    _type = data.get('type')
    _timestamp = arrow.get(data['timestamp']).to("Asia/Kolkata").datetime

    try:
        comm_obj = CommunicationLog.objects.get(channel='whatsapp', message_id=mid)
        if _type == "message_api_sent":
            comm_obj.status = "SENT"
            comm_obj.sent_on = _timestamp
        elif _type == "message_api_delivered":
            comm_obj.status = "DELIVERED"
            comm_obj.delivered_on = _timestamp
        elif _type == "message_api_read":
            comm_obj.status = "READ"
            comm_obj.read_on = _timestamp
        elif _type == "message_api_failed":
            comm_obj.status = "FAILED"
            method_name = 'event_{}_channel_{}'.format(comm_obj.event, 'sms')
            if hasattr(comm_obj.content_object, method_name):
                method = getattr(comm_obj.content_object, method_name)
                method()

        comm_obj.save()
    except CommunicationLog.DoesNotExist:
        if _type == "message_received":
            if data["data"]["customer"]["phone_number"] == "7717262764":
                 chatbot_view(data)




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


@ensure_db_connection
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
        if file_extension == 'plain': continue

        if file_extension not in ('pdf',):
            if not len(doc_file.content) <= 512000:
                print("File To Be Compressed: {} Original Size: {}".format(doc.link, len(doc_file.content)))
                response = requests.get("{}{}".format(settings.THUMBOR_URL_LOCAL_INTERNAL_WEBP_COMPRESSED, doc.link))
            else:
                print("File To Be Converted To Webp Format {}".format(doc.link))
                response = requests.get("{}{}".format(settings.THUMBOR_URL_LOCAL_INTERNAL_WEBP_COMPRESSED, doc.link))

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


def interakt_flow_template(session_id):
    body_text = {
        "countryCode": "+91",
        "phoneNumber": session_id,
        "fullPhoneNumber": " ",
        "campaignId": "YOUR_CAMPAIGN_ID",
        "callbackData": "some text here",
        "type": "Template",
        "template": {
            "name": "address_details",
            "languageCode": "hi",
            "bodyValues": [
                "body_variable_value_1",
                "body_variable_value_n"
            ]
        }
    }


    track.client.post(
        api_key=settings.INTERAKT_API_KEY,
        path="/v1/public/message/",
        body=body_text
    ).json()

    logger.info(f'Sending message to Whatapp: send flow to  {session_id}')


def redis_image(url):
    redis_conn = django_rq.get_connection("default")
    match = re.search(r'^.+\.jpeg', url)

    if match:
        result = match.group(0)
        print(result)

    redis_conn.set(result, url)

    my_redis_data = redis_conn.get(result)
    print(f'the stored data in redis is {result}: {my_redis_data}')
    return result

def dialogflow_whatapp_message(reply, session_id, user_id):
    body_text = {
        "userId": user_id or " ",
        "fullPhoneNumber": f'+91{session_id}',
        "callbackData": "some_callback_data",
        "type": "Text",
        "data": {
            "message": reply
        }
    }
    track.client.post(
        api_key=settings.INTERAKT_API_KEY,
        path="/v1/public/message/",
        body=body_text
    ).json()

    logger.info(f'Sending message to Whatapp:  {reply} from {session_id}')


def detect_intent_texts(project_id, session_id, text, language_code='hi'):
    client = dialogflow.SessionsClient()
    session = client.session_path(project_id, session_id)
    if not text:
        raise ValueError("Input text is empty. Please provide a valid text input.")

    text_input = dialogflow.TextInput(text=text, language_code=language_code)
    query_input = dialogflow.QueryInput(text=text_input)

    response = client.detect_intent(
        request={"session": session, "query_input": query_input}
    )

    return response.query_result


def chatbot_view(data_dict):
    data = data_dict['data']
    message_data = data.get('message', {})
    message_content = message_data["message_content_type"]
    user_message = redis_image(message_data['media_url']) if 'media_url' in message_data else message_data.get('message', ' ')
    project_id = 'om-prakash-rerm'
    user_id = data['customer']["id"]
    session_id = data['customer']['phone_number']
    print(f'the user pin is : {user_message}')
    if message_content == "InteractiveFlowReply":
        response_json_data = json.loads(user_message["nfm_reply"]["response_json"])
        logger.info(f'the response data that we get is : {response_json_data.get("data")}')
        reply = WhatsappPreInspection(Inspection_data=response_json_data.get("data" ,""), unique_id=session_id, intent="address_details")
        logger.info(f'handling flow response to fill the address form')
    else:
        logger.info(f"Sending message to Dialogflow: {user_message} from {session_id}")
        # You can use a unique ID for each user session
        response = detect_intent_texts(project_id, session_id, user_message)
        reply = response.fulfillment_text

    if reply:
        try:
            dialogflow_whatapp_message(reply, session_id, user_id)
            print(f"Message sent successfully: {reply}")  # Logging example
        except Exception as e:
            print(f"Error sending message: {str(e)}")
