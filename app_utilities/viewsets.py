import base64
import datetime
import time

import requests
from django.http import JsonResponse, HttpRequest
from rest_framework import viewsets
from rest_framework.decorators import action

from app_utilities.enums import AppUtilitiesErrorApplicationEnum
from app_utilities.models import UjjwalaApplicationOcrErrorLogs
from utils.image_utils import compress_file
from utils.zoho_catalyst import ZohoCatalyst, zoho_client
import logging


class ApplicationUtilitiesAPIViewSet(viewsets.ViewSet):
	@action(methods=['post'], detail=False, url_path='get_details_for_aadhar')
	def get_details_for_aadhar(self, request: HttpRequest, *args, **kwargs):
		zoho_logger = logging.Logger("zoho_uid_details_api")
		t0 = time.time()

		uid_front_url = request.data.get('uid_front_url')
		uid_back_url = request.data.get('uid_back_url')

		# res = requests.head(uid_front_url, headers={"Tus-Resumable": "1.0.0"})
		# header_info = res.headers
		# file_type = header_info['Upload-Metadata'].split(',')[0].split(' ')[1]
		# if 'webp' in base64.b64decode(file_type).decode():
		# 	uid_front_url = 'http://dca.arungas.com:6988/unsafe/filters:format(jpeg)/{}'.format(uid_front_url)
		# result, uid_front_url, uid_front_file_size = compress_file(uid_front_url)
		#
		# res = requests.head(uid_back_url, headers={"Tus-Resumable": "1.0.0"})
		# header_info = res.headers
		# file_type = header_info['Upload-Metadata'].split(',')[0].split(' ')[1]
		# if 'webp' in base64.b64decode(file_type).decode():
		# 	uid_back_url = 'http://dca.arungas.com:6988/unsafe/filters:format(jpeg)/{}'.format(uid_back_url)
		# result, uid_back_url, uid_back_file_size = compress_file(uid_back_url)
		generated_on = datetime.datetime.now()
		response = zoho_client.get_details_from_aadhaar(uid_front_url, uid_back_url)
		t1 = time.time()

		time_difference = t1 - t0
		zoho_logger.info(time_difference)
		print("Time Taken For Zoho API{}".format(time_difference))
		response.update({
			"uid_front_url": uid_front_url,
			"uid_back_url": uid_back_url,
		})
		UjjwalaApplicationOcrErrorLogs.objects.create(
			generated_on=generated_on,
			wait_time=time_difference,
			status=response.get('status', ''),
			uid_front_url=uid_front_url,
			uid_back_url=uid_back_url,
			data=response
		)
		print(response)
		return JsonResponse(response, safe=False)
