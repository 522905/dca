from django.test import TestCase

# Create your tests here.
from communication_log.views import interakt_webhook, infobip_webhook
from communication_log.models import CommunicationLog
from django.test import RequestFactory, TestCase


class CommunicationLogTestCase(TestCase):

    def setUp(self):
        self.commlog = CommunicationLog.objects.create(event="submit", channel="whatsapp", message_id="123")
        self.factory = RequestFactory()

        self.commlog = CommunicationLog.objects.create(event="submit", channel="sms", message_id="321")
        self.factory = RequestFactory()

    def test_webhook_call(self):

        data ="""
           {
  "version": "1.0",
  "timestamp": "2021-11-04T00:00:00.000+0000",
  "type": "message_api_sent",
  "data": {
    "customer": {
      "id": "0000-0000-00000-0000",
      "channel_phone_number": "910000000000"
    },
    "message": {
      "id": "123",
      "chat_message_type": "AgentMessage",
      "channel_failure_reason": null,
      "message_status": "Read",
      "received_at_utc": "2021-11-02T07:05:15.930+0000",
      "delivered_at_utc": "2021-11-02T07:05:17.899+0000",
      "seen_at_utc": "2021-11-02T07:05:22.352+0000",
      "campaign_id": null,
      "is_template_message": true,
      "raw_template": null,
      "channel_error_code": null,
      "message_content_type": "Template",
      "metadata": {
        "source": "PublicInterakt"
      }
    }
  }
}
    """

        request = self.factory.post('/commlog/interakt/webhook/',data=data,
                                content_type='application/json')
        response = interakt_webhook(request, is_async=False)
        obj = CommunicationLog.objects.get(message_id="123")
        self.assertEqual(obj.status, "SENT")


class CommunicationLogTestCaseSms(TestCase):

    def setUp(self):
        self.commlog = CommunicationLog.objects.create(event="submit", channel="sms", message_id="321")
        self.factory = RequestFactory()

    def test_webhook_infobip_call(self):
        data ="""
           {
        "bulkId": "1478260834465349757",
        "messages": [
            {
                "to": "41793026727",
                "status": {
                    "groupId": 1,
                    "groupName": "EXPIRED",
                    "id": 7,
                    "name": "EXPIRED",
                    "description": "Message sent to next instance"
                },
                "smsCount": 1,
                "messageId": "321"
            }
        ]
    }
    """

        request = self.factory.post('/commlog/infobip/webhook/', data=data,
                                content_type='application/json')
        response = infobip_webhook(request, is_async=False)
        obj = CommunicationLog.objects.get(message_id="321")
        self.assertEqual(obj.status, "FAILED")
