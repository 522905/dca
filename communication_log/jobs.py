from django_rq import job
from communication_log.models import CommunicationLog


# @job
def interakt_webhook_job_processing(data):
    mid = data['data']['message']['id']
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


