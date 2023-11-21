import datetime
import io

import django_filters
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination

from ujjwala import models
from ujjwala.enums import SVSDMSStatusEnum, UjjwalaApplicationDocumentsEnum, \
	DisbursementDriveStatusEnum
from ujjwala.models import ConnectionDisbursement, DisbursementDrive
from ujjwala.serializers import UjjwalaV2ApplicationSerializer
from ujjwala.ujjwala_functions import download_installation_form
from utils.global_functions import upload_file_type_obj_to_minio_bucket, upload_file_to_minio_bucket
from utils.qrcode import append_qr_code_to_sv


class CustomPagePagination(PageNumberPagination):
	page_size_query_param = 'page_size'
	page_size = 50


class UjjwalaApplicationSVViewSet(viewsets.ModelViewSet):
	queryset = models.UjjwalaV2Application.objects.all()
	serializer_class = UjjwalaV2ApplicationSerializer
	filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
	filterset_fields = ['id', 'status']
	ordering_fields = '__all__'
	pagination_class = CustomPagePagination

	@action(methods=['post'], detail=True, url_path='sv_document_status')
	def sv_document_status(self, request, *args, **kwargs):
		from ujjwala.models import UjjwalaV2Application, ConnectionDisbursementInvitation, ConnectionDisbursement

		sv_status = request.data.get('sv_status')
		booking_id = request.POST.get('booking_id', None)
		consumer_disbursement_id = request.POST.get('connection_disbursement_id')
		ci_obj = ConnectionDisbursement.objects.get(id=consumer_disbursement_id)

		if not ci_obj.documents.filter(type=UjjwalaApplicationDocumentsEnum.INSTALLATION_DOCUMENT).exists():
			# Installation Form Upload
			installation_document = download_installation_form(ci_obj.parent)
			upload_url = upload_file_to_minio_bucket(
				installation_document,
				"ujjwaladocuments",
				"ujjwala_{}_installation_document".format(ci_obj.parent_id)
			)
			ci_obj.documents.create(
				type=UjjwalaApplicationDocumentsEnum.INSTALLATION_DOCUMENT,
				link=upload_url
			)

		invitation: ConnectionDisbursementInvitation = ci_obj.invitation.filter(status='VALID').order_by('-id').first()

		if not invitation:
			invitation = ConnectionDisbursementInvitation(
				booking_id=booking_id,
				parent=ci_obj
			)

		if sv_status == 'Downloaded':
			file = request.FILES.get('file')
			pdf_file_bytes = io.BytesIO(file.read())
			bytes_stream = append_qr_code_to_sv(
				"{},SV".format(ci_obj.parent_id),
				booking_id,
				pdf_file_bytes
			)
			# Bucket Name: ujjwaladocuments
			doc_file_bytes = io.BytesIO(bytes_stream)
			sv_upload_link = upload_file_type_obj_to_minio_bucket(
				doc_file_bytes, 'ujjwaladocuments', "sv_{}".format(ci_obj.parent_id), "application/pdf"
			)
			invitation.sv_link = sv_upload_link
			invitation.sv_uploaded_on = datetime.datetime.now()
			invitation.sv_sdms_status = SVSDMSStatusEnum.DOWNLOADED
			invitation.robo_error_message = None
		elif sv_status == 'Queued':
			invitation.sv_sdms_status = SVSDMSStatusEnum.DOWNLOAD_QUEUED
			invitation.booking_id = booking_id
			invitation.robo_error_message = None
		elif sv_status == 'Generated':
			invitation.sv_sdms_status = SVSDMSStatusEnum.GENERATED
			invitation.booking_id = booking_id
			invitation.robo_error_message = None
		elif sv_status == 'Failed':
			invitation.sv_sdms_status = SVSDMSStatusEnum.FAILED
			invitation.robo_error_message = request.POST.get('error_message', '')
		invitation.sv_sdms_updated_on = datetime.datetime.now()
		invitation.save()

		return HttpResponse('OK')


	@action(methods=['get'], detail=False, url_path='get_pending_sv_records')
	def get_pending_sv_records(self, request, *args, **kwargs):
		sv_status = request.GET.get('sv_status')
		filters = {}

		if request.GET.get('cdid', ''):
			filters['disbursement_drive__in'] = request.GET.get('cdid').split(',')

		connection_disbursement_list = ConnectionDisbursement.objects.filter(
			**filters
		).filter(
			invitation__sv_sdms_status__in=sv_status.split(','),
			disbursement_drive__status=DisbursementDriveStatusEnum.ACTIVE
		).order_by('walk_in_date')

		page = self.paginate_queryset(connection_disbursement_list)
		return self.get_paginated_response([
			{
				"payload": {
					'connection_disbursement_id': record.id,
					'application_id': record.parent_id,
					'consumer_id': record.parent.consumer_id,
					'name': record.parent.name,
					'product': record.parent.product,
					'sv_sdms_updated_on': record.invitation.filter(status='VALID').order_by(
						                                 '-id').first().sv_sdms_updated_on,
					'report_name': "{}DCA_{}".format(record.parent.id,
					                                 record.invitation.filter(status='VALID').order_by(
						                                 '-id').first().booking_id)
				}
			} for record in page
		])

	@action(methods=['get'], detail=False, url_path='get_walk_in_no_sv_list')
	def get_walk_in_no_sv_list(self, request, *args, **kwargs):
		filters = {}

		if request.GET.get('cdid', ''):
			filters['disbursement_drive__in'] = request.GET.get('cdid').split(',')

		connection_disbursement_list = ConnectionDisbursement.objects.filter(
			disbursement_drive__status=DisbursementDriveStatusEnum.ACTIVE,
			**filters
		).filter(
			Q(invitation=None) | Q(invitation__sv_sdms_status=SVSDMSStatusEnum.NOT_GENERATED)
		).order_by(
			'walk_in_date'
		)

		page = self.paginate_queryset(connection_disbursement_list)
		return self.get_paginated_response([
			{
				"payload": {
					'connection_disbursement_id': record.id,
					'application_id': record.parent_id,
					'consumer_id': record.parent.consumer_id,
					'name': record.parent.name,
					'product': record.parent.product
				}
			} for record in page
		])
