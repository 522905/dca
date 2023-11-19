import datetime
import io

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala.enums import UjjwalaV2ApplicationStatus, SVSDMSStatusEnum, UjjwalaApplicationDocumentsEnum
from ujjwala.ujjwala_functions import omc_nic_status_update, download_installation_form
from utils.global_functions import upload_file_type_obj_to_minio_bucket, upload_file_to_minio_bucket
from utils.qrcode import append_qr_code_to_sv


class UjjwalaApplicationSVViewSet(viewsets.ViewSet):
	@action(methods=['post'], detail=True, url_path='sv_document_status')
	def sv_document_status(self, request, *args, **kwargs):
		from ujjwala.models import UjjwalaV2Application, ConnectionDisbursementInvitation, ConnectionDisbursement

		application: UjjwalaV2Application = UjjwalaV2Application.objects.get(pk=kwargs.get('pk'))
		invitation: ConnectionDisbursementInvitation = application.connection_disbursement.invitation.filter(
			status='VALID').first()
		if not invitation:
			consumer_disbursement_id = request.POST.get('connection_disbursement_id')
			obj = ConnectionDisbursement.objects.filter(id=consumer_disbursement_id).first()
			if not obj:
				return HttpResponse('Connection Disbursement Not Found')

			sv_upload_link = None
			booking_id = request.POST.get('booking_id', None)

			if not request.POST.get('sv_generated_not_downloaded'):
				file = request.FILES.get('file')
				pdf_file_bytes = io.BytesIO(file.read())
				bytes_stream = append_qr_code_to_sv(
					"{},SV".format(obj.parent_id),
					booking_id,
					pdf_file_bytes
				)
				# Bucket Name: ujjwaladocuments
				doc_file_bytes = io.BytesIO(bytes_stream)
				sv_upload_link = upload_file_type_obj_to_minio_bucket(
					doc_file_bytes, 'ujjwaladocuments', "sv_{}".format(obj.parent_id), "application/pdf"
				)

			# Installation Form Upload
			installation_document = download_installation_form(obj.parent)
			upload_url = upload_file_to_minio_bucket(
				installation_document,
				"ujjwaladocuments",
				"ujjwala_{}_installation_document".format(obj.parent_id)
			)
			obj.documents.create(
				type=UjjwalaApplicationDocumentsEnum.INSTALLATION_DOCUMENT,
				link=upload_url
			)

			invitation = obj.invitation.create(
				sv_link=sv_upload_link if sv_upload_link else '',
				booking_id=booking_id,
				sv_uploaded_on=datetime.datetime.now() if sv_upload_link else None
			)

		sv_status = request.data.get('sv_status')
		if sv_status == 'Downloaded':
			invitation.sv_sdms_status = SVSDMSStatusEnum.GENERATED_DOWNLOADED
		elif sv_status == 'Queued':
			invitation.sv_sdms_status = SVSDMSStatusEnum.GENERATED_NOT_DOWNLOADED_PRINTED
		else:
			invitation.sv_sdms_status = SVSDMSStatusEnum.GENERATED_NOT_DOWNLOADED_NOT_PRINTED
		invitation.save()
		return HttpResponse('OK')
