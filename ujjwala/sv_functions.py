import io

import requests

from ujjwala.ujjwala_functions import download_installation_form
from utils.global_functions import upload_file_to_minio_bucket, upload_file_type_obj_to_minio_bucket
from utils.qrcode import append_qr_code_to_sv


def create_installation_document(connection_disbursement_id):
	from ujjwala.models import ConnectionDisbursement
	from ujjwala.enums import UjjwalaApplicationDocumentsEnum

	ci_obj = ConnectionDisbursement.objects.get(id=connection_disbursement_id)

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


def update_sv_document(connection_disbursement_id, booking_id, content):
	from ujjwala.models import ConnectionDisbursement

	ci_obj = ConnectionDisbursement.objects.get(id=connection_disbursement_id)
	pdf_file_bytes = io.BytesIO(content)
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
	return sv_upload_link


def update_in_dca(connection_disbursement_id, booking_id, sv_upload_link, consumer_id):

	data = {
		"connection_disbursement_id": connection_disbursement_id,
		"booking_id": booking_id,
		"sv_upload_link": sv_upload_link,
		"consumer_id": consumer_id
	}
	url = "https://dca.arungas.com/ujjwala/sv-bot/invitation_update/"
	# url = "http://192.168.168.4:60610/ujjwala/sv-bot/invitation_update/"
	res = requests.post(f"{url}", json=data)
	res.raise_for_status()
	return res.json()
	# from ujjwala.models import ConnectionDisbursement, ConnectionDisbursementInvitation
	#
	# ci_obj = ConnectionDisbursement.objects.get(id=connection_disbursement_id)
	#
	# invitation = ci_obj.invitation.filter(status='VALID').order_by('-id').first()
	# if not invitation:
	# 	invitation = ConnectionDisbursementInvitation.objects.create(
	# 		parent=ci_obj,
	# 		booking_id=booking_id,
	# 		sv_link=sv_upload_link
	# 	)
	# else:
	# 	invitation.booking_id = booking_id
	# 	invitation.sv_link = sv_upload_link
	# 	invitation.save()
	#
	# return invitation

