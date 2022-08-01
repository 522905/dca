from django.http import JsonResponse, HttpRequest
from rest_framework import viewsets
from rest_framework.decorators import action

from utils.zoho_catalyst import ZohoCatalyst, zoho_client


class ApplicationUtilitiesAPIViewSet(viewsets.ViewSet):
	@action(methods=['post'], detail=False, url_path='get_details_for_aadhar')
	def get_details_for_aadhar(self, request: HttpRequest, *args, **kwargs):
		uid_front_url = request.data.get('uid_front_url')
		uid_back_url = request.data.get('uid_back_url')

		result = zoho_client.get_details_from_aadhaar(uid_front_url, uid_back_url)

		return JsonResponse(result, safe=False)
