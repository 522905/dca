import json

from django.http import HttpRequest
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from otp.models import Otp
from otp.serializer import CreateOtpSerializer, VerifyOtpSerializer, SendOtpSerializer, \
	GetOtpVerificationPhonesSerializer, OtpAdditionRequest


class OtpViewSet(viewsets.ViewSet):
	permission_classes = (permissions.AllowAny,)

	@action(methods=['post'], detail=False)
	def generate(self, request: HttpRequest, *args, **kwargs):
		otp_serializer = CreateOtpSerializer(data=request.data)
		otp_serializer.is_valid(raise_exception=True)
		otp_obj = otp_serializer.save()

		send_otp_serializer = SendOtpSerializer(data={'reference_number': otp_obj.pk})
		send_otp_serializer.is_valid(raise_exception=True)
		res = send_otp_serializer.send()

		return Response(status=200, data={
			'status': 200 if res else 400,
			'msg': 'Sent' if res else 'Something went wrong with SMS gateway',
			'data': otp_serializer.data
		})

	@action(methods=['post'], detail=False)
	def verify(self, request: HttpRequest, *args, **kwargs):
		verify_otp_serializer = VerifyOtpSerializer(data=request.data)
		verify_otp_serializer.is_valid(raise_exception=True)
		verified, msg = verify_otp_serializer.verify()

		if verified:
			return Response(status=200, data={'status': 200, 'msg': msg})

		return Response(status=200, data={'status': 400, 'msg': msg})

	# @action(methods=['post'], detail=True)
	# def call(self, request, *args, **kwargs):
	# 	otpUniqueId = 'DEL983687'
	# 	#resend otp
	# 	return Response({})

	@action(methods=['post'], detail=False)
	def resend(self, request, *args, **kwargs):
		send_otp_serializer = SendOtpSerializer(data=request.data)
		send_otp_serializer.is_valid(raise_exception=True)
		res = send_otp_serializer.send()
		return Response(status=200, data={
			'status': 200 if res else 400,
			'msg': 'Sent' if res else 'Something went wrong with SMS gateway'
		})


class GetNumbersViewSet(APIView):
	permission_classes = (permissions.AllowAny,)

	def get(self, request, *args, **kwargs):
		serializer = GetOtpVerificationPhonesSerializer(data=request.GET)
		serializer.is_valid(raise_exception=True)
		return Response(serializer.get_numbers())

	@action(methods=['post'], detail=False)
	def create_addition_request(self, *args, **kwargs):
		otp_req = OtpAdditionRequest(data=self.request.data)
		otp_req.is_valid(raise_exception=True)
		res = otp_req.save()
		return Response(status=200, data=res)

