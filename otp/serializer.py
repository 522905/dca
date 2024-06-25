import random
import string
from datetime import timedelta

import requests
import track
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.timezone import now
from rest_framework import serializers

from communication_log.models import CommunicationLog
from otp.enums import OtpChannels
from otp.models import Otp



def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))


def __get_ref_no__():
	return 'DL{}{}'.format(
		timezone.now().strftime('%y%m%d'),
		id_generator(4, chars=string.ascii_uppercase)
	).upper()


class CreateOtpSerializer(serializers.ModelSerializer):
	class Meta:
		model = Otp
		fields = ('reference_number', 'mobile', 'channel', 'extra', 'variables', 'valid_till', 'closed')
		read_only_fields = ('reference_number', 'valid_till', 'closed')
		extra_kwargs = {
			# 'otp': {'write_only': True},
		}

	def create(self, validated_data, *args, **kwargs):
		data = dict(validated_data)

		ref_no = None
		while True:
			ref_no = __get_ref_no__()
			try:
				Otp.objects.get(reference_number=ref_no)
			except Otp.DoesNotExist:
				break

		data['reference_number'] = ref_no

		data['otp'] = id_generator(4, chars=string.digits)
		data['valid_till'] = timezone.now() + timedelta(minutes=5)
		data['closed'] = False

		return super(CreateOtpSerializer, self).create(data, *args, **kwargs)


class VerifyOtpSerializer(serializers.Serializer):
	reference_number = serializers.PrimaryKeyRelatedField(
		queryset=Otp.objects.filter(closed=False)
	)
	otp = serializers.CharField()

	def verify(self):
		otp_obj: Otp = self.validated_data.get('reference_number')
		verified, msg = otp_obj.verify_and_close(self.validated_data.get('otp'))
		return verified, msg


DELIVERY_SMS_TEMPLATE = \
	"Ujjwala Pre Inspection Process" \
	"Your otp is {otp} " \
	"valid for {expiry_in_min}m RefNo {reference_number}."


class SendOtpSerializer(serializers.Serializer):
	reference_number = serializers.PrimaryKeyRelatedField(
		queryset=Otp.objects.filter(closed=False)
	)

	def send(self):
		otp_obj: Otp = self.validated_data.get('reference_number')

		# context = {
		# 	"otp": otp_obj.otp,
		# 	"expiry_in_min": round((otp_obj.valid_till - now()).total_seconds() / 60),
		# 	"reference_number": otp_obj.reference_number,
		# }

		if otp_obj.channel == OtpChannels.WHATSAPP:
			body_text = {
				"countryCode": "+91",
				"phoneNumber": otp_obj.mobile,
				"type": "Template",
				"traits": {
					"name": otp_obj.mobile,
				},
				# "callbackData": "some_callback_data",
				"template": {
					# "name": "ujjwala_application_submitted_",
					"name": "ujjwala_pre_inspection_otp",
					"languageCode": "hi",
					"headerValues": [
						# "Alert",  #
					],
					"bodyValues": [
						otp_obj.otp
					]
				}
			}

			ujjwala_v2_application_content_type = ContentType.objects.get(
				app_label='ujjwala', model='ujjwalav2application'
			)
			data = track.client.post(
				api_key=settings.INTERAKT_API_KEY,
				path="/v1/public/message/",
				body=body_text
			).json()

			if data['result']:
				CommunicationLog.objects.create(
					content_type=ujjwala_v2_application_content_type,
					object_id=self.pk,
					event="pre_inspection_otp", channel="whatsapp",
					message_id=data.get('id')
				)
		elif otp_obj.channel == OtpChannels.SMS:
			pass
			# message = DELIVERY_SMS_TEMPLATE.format(**context)
		else:
			pass



		# "sendAt": "2021-08-25T16:00:00.000+0000",
		# "deliveryTimeWindow": {
		# 	"from": {
		# 		"hour": 6,
		# 		"minute": 0
		# 	},
		# 	"to": {
		# 		"hour": 15,
		# 		"minute": 30
		# 	},
		# 	"days": [
		# 		"MONDAY",
		# 		"TUESDAY",
		# 		"WEDNESDAY",
		# 		"THURSDAY",
		# 		"FRIDAY",
		# 		"SATURDAY",
		# 		"SUNDAY"
		# 	]
		# }
		# "language": {
		# 	"languageCode": "TR"
		# },
		# "transliteration": "TURKISH",

		# x = requests.post("https://4r198.api.infobip.com/sms/2/text/advanced", json={
		# 	"messages": [
		# 		{
		# 			"from": "ARUNGS",
		# 			"destinations": [
		# 				{
		# 					"to": "+91{}".format('7888691902')#otp_obj.mobile),
		# 					# "messageId": "MESSAGE-ID-123-xyz"
		# 				}
		# 			],
		#
		# 			"text": message,
		# 			"flash": False,
		#
		# 			"regional": {
		# 				"indiaDlt": {
		# 					"principalEntityId": "1101546710000030317",
		# 					"contentTemplateId": "1107161183026272363"
		# 				}
		# 			}
		#
		# 			# "intermediateReport": True,
		# 			# "notifyUrl": "https://www.example.com/sms/advanced",
		# 			# "notifyContentType": "application/json",
		# 			# "callbackData": "DLR callback data",
		# 			# "validityPeriod": 720
		# 		}
		# 	]
		# }, headers={
		# 	'Authorization': 'App 140a3abf6dd9134f5defb703a54dfcf0-e3df520b-f144-4282-a174-aa3765c7b438'
		# })
		x = ''
		print(x)

		return x.text


class GetOtpVerificationPhonesSerializer(serializers.Serializer):
	contact_mobile = serializers.CharField()
	uid_linked_mobile = serializers.CharField()

	def get_numbers(self):
		from ujjwala.models import UjjwalaV2Application

		parent_id = self.validated_data.get('parent_id')
		application = UjjwalaV2Application.objects.filter(pk=parent_id)
		numbers = [application.contact_mobile, application.uid_linked_mobile]
		return numbers


class OtpAdditionRequest(serializers.Serializer):
	customer_id = serializers.CharField()
	address_id = serializers.CharField()
	contact_name = serializers.CharField()
	contact_number = serializers.CharField()

	def save(self):
		process_id = "6d7a0724-4348-4522-b863-445d5dde659b"
		created_on = "2021-02-01T14:02"
		return {
			"msg": "DAC Addition Request Generated {} at {}".format(process_id, created_on),
			"data": {
				'process_id': process_id,
				"created_on": created_on
			}
		}
