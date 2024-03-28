import datetime
import json
import time
from functools import partial

import django_rq
import requests
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from ujjwala.enums import PreInspectionStatusEnum, ConnectionDisbursementStatusEnum, UjjwalaApplicationDocumentsEnum, \
	PreInspectionRejectionReasonsEnum, product_quantity_map, UjjwalaV2ApplicationStatus
from ujjwala.models import PreInspectionDocuments, BankDetailsUpdateRequest
from ujjwala.ujjwala_functions import re_create_legal_docs, download_ujjwala_physical_legal_docs, get_circles_intersect, \
	get_area_tag
from ujjwala.vici_functions import add_lead_to_vicidial_list, delete_lead_from_vicidial_list
from utils.global_functions import upload_file_to_minio_bucket

VICIDIAL_LIST = 1201


def preinspection_update_review_address_accepted(application_id, review_address_completed_by):
	from ujjwala.models import UjjwalaV2Application

	app_obj = UjjwalaV2Application.objects.get(pk=application_id)
	app_obj.address_verified = True
	app_obj.address_verified_by = review_address_completed_by
	app_obj.address_verified_on = datetime.datetime.now()
	app_obj.save()


def preinspection_evaluate_pre_inspection_data(preinspection_id):
	from ujjwala.models import PreInspection, ConnectionDisbursement, ConnectionDisbursementInvitation
	from django_fsm_log.models import StateLog

	# Evaluate If Address Needs To Be Verified
	pi_obj = PreInspection.objects.get(pk=preinspection_id)

	area_tag = get_area_tag(pi_obj.id)
	pi_obj.tags.add(area_tag)
	pi_obj.save()
	action_address_accept = False
	old_address_json = {}

	safety_audio = pi_obj.documents.filter(type=UjjwalaApplicationDocumentsEnum.SAFETY_AUDIO).first()

	family_members = []

	for family_member in pi_obj.parent.family_members.all():
		family_members.append({
			"relation": family_member.relation,
			"name": family_member.name,
			'dob': family_member.dob.strftime("%Y-%m-%d"),
			'uid_no': family_member.uid_no,
			"uid_front_link": family_member.uid_front_link,
			"uid_back_link": family_member.uid_back_link,
		})

	if pi_obj.address_updated:
		state_log = StateLog.objects.filter(source_state=PreInspectionStatusEnum.CHANGE_ADDRESS,
		                                    content_type_id=ContentType.objects.get(
			                                    app_label='ujjwala', model='preinspection'
		                                    ),
		                                    object_id=preinspection_id).order_by("-id").first()
		old_address_json = eval(state_log.description) if state_log else {}

		if pi_obj.parent.address_verified:
			address_matched = True

			address_json = pi_obj.parent.address_json
			address_json.pop('room_no')
			address_json.pop('floor')
			for k, v in address_json.items():
				if not old_address_json.get(k) == v:
					address_matched = False
					break

			intersect = False
			if pi_obj.parent.latitude and pi_obj.parent.longitude:
				intersect = get_circles_intersect(
					float(pi_obj.latitude), float(pi_obj.longitude), float(pi_obj.accuracy.replace("m", "")),
					float(pi_obj.parent.latitude), float(pi_obj.parent.longitude),
					float(pi_obj.parent.accuracy.replace("m", ""))
				)

			action_address_accept = (address_matched and intersect)

	sv_generated = False
	ci_obj: ConnectionDisbursement = ConnectionDisbursement.objects.filter(parent=pi_obj.parent_id).first()
	if ci_obj:
		cii_obj: ConnectionDisbursementInvitation = ConnectionDisbursementInvitation.objects.filter(
			parent_id=ci_obj.id).first()
		if cii_obj:
			sv_generated = True if cii_obj.sv_link else False

	variables = {
		"address_json": {"value": json.dumps(pi_obj.parent.address_json), "type": "String"},
		"old_address_json": {"value": json.dumps(old_address_json) if old_address_json else "", "type": "String"},
		"latitude": {"value": pi_obj.latitude, "type": "String"},
		"longitude": {"value": pi_obj.longitude, "type": "String"},
		"accuracy": {"value": pi_obj.accuracy, "type": "String"},
		"application_id": {"value": pi_obj.parent_id, "type": "String"},
		"name": {"value": pi_obj.parent.name, "type": "String"},
		"kitchen_photo": {
			"value": pi_obj.documents.get(type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO).link},
		"main_gate_photo": {
			"value": pi_obj.documents.get(type=UjjwalaApplicationDocumentsEnum.MAIN_GATE).link},
		"profile_photo": {
			"value": pi_obj.parent.document_self()},
		"safety_audio": {"value": safety_audio.link if safety_audio else ""},
		"contact_mobile": {"value": pi_obj.parent.contact_mobile},
		"family_members": {"value": json.dumps(family_members)},
		"source": {"value": 'PREINSPECTION', "type": "String"},
		"mechanic": {"value": "{} {}".format(pi_obj.mechanic.first_name,
		                                     pi_obj.mechanic.last_name) if pi_obj.mechanic else "Self",
		             "type": "String"},
		"area_name": {"value": area_tag, "type": "String"},
		"review_address_status": {"type": "String", "value": 'MATCHED' if action_address_accept else 'NOT_MATCHED'},
		"other_details_status": {"type": "String",
		                         "value": 'MATCHED' if pi_obj.parent.other_members_verified else 'NOT_MATCHED'},
		"sv_generated": {"type": "Boolean", "value": sv_generated},
		"referral_code": {"type": "String", "value": pi_obj.parent.referral_code}
	}
	return variables


def preinspection_update_family_members(preinspection_id, family_members):
	from ujjwala.models import PreInspection

	pi_obj = PreInspection.objects.get(pk=preinspection_id)
	fm_list = pi_obj.parent.family_members.all()

	for family_member in family_members:
		fm_obj = fm_list.get(relation=family_member['relation'])
		fm_obj.name = family_member['name']
		fm_obj.dob = family_member['dob']
		fm_obj.uid_no = family_member['uid_no']
		fm_obj.uid_front_link = family_member['uid_front_link']
		fm_obj.uid_back_link = family_member['uid_back_link']
		fm_obj.save()


def preinspection_update_other_details_action(review_other_details_completed_by, preinspection_id,
                                              other_details_action, remarks):
	from ujjwala.models import PreInspection

	pi_obj = PreInspection.objects.get(pk=preinspection_id)
	if other_details_action == 'ACCEPTED' or other_details_action == "":
		pi_obj.parent.other_members_verified = True
		pi_obj.parent.other_members_verified_on = datetime.datetime.now()
		pi_obj.parent.save()
		pi_obj.save()
	elif other_details_action == 'ON_HOLD':
		if pi_obj.parent.status != 'ON_HOLD':
			pi_obj.parent.transition_on_hold(description=json.dumps(
				{"reason": remarks, "review_other_details_completed_by": review_other_details_completed_by}))
			pi_obj.parent.save()


def preinspection_update_in_dca(review_variables, preinspection_id, action, rejected_reasons=None):
	from ujjwala.models import PreInspection

	pi_obj = PreInspection.objects.get(pk=preinspection_id)

	review_address_completed_by = review_variables.get('review_address_completed_by')
	review_other_details_completed_by = review_variables.get('review_other_details_completed_by')
	review_pre_inspection_completed_by = review_variables.get('review_pre_inspection_completed_by')

	if action == 'OUT_OF_SERVICE_AREA':
		if not pi_obj.parent.status == 'ON_HOLD':
			pi_obj.parent.transition_on_hold(description=json.dumps(
				{"reason": "Out Of Service Area", "review_address_completed_by": review_address_completed_by}))
			pi_obj.parent.save()
		return
	elif action == 'PREINSPECTION_REJECT':
		rejected_reasons = [PreInspectionRejectionReasonsEnum.CONDITION_LOCATION_MISMATCH]
		pi_obj.pre_inspection_review(rejected_reasons=rejected_reasons, description=json.dumps(
			{"reason": [PreInspectionRejectionReasonsEnum.CONDITION_LOCATION_MISMATCH],
			 "review_address_completed_by": review_address_completed_by}))
		pi_obj.save()
		return

	if rejected_reasons:
		description = json.dumps(
			{
				"reasons": rejected_reasons,
				"review_address_completed_by": review_address_completed_by,
				"review_other_details_completed_by": review_other_details_completed_by,
				"review_pre_inspection_completed_by": review_pre_inspection_completed_by
			}
		)

		pi_obj.pre_inspection_review(review_status='REJECTED', rejected_reasons=rejected_reasons,
		                             description=description)
	else:
		description = json.dumps(
			{
				"review_address_completed_by": review_address_completed_by,
				"review_other_details_completed_by": review_other_details_completed_by,
				"review_pre_inspection_completed_by": review_pre_inspection_completed_by
			}
		)

		pi_obj.pre_inspection_review(review_status='ACCEPTED', rejected_reasons=[], description=description)



def preinspection_create_legal_docs(preinspection_id):
	from ujjwala.models import PreInspection, ConnectionDisbursement

	pi_obj = PreInspection.objects.get(pk=preinspection_id)

	if pi_obj.parent.status in (
		UjjwalaV2ApplicationStatus.APPLICATION_REJECTED, UjjwalaV2ApplicationStatus.AUDIT_APPLICATION):
		return True
	# Bucket Name: ujjwaladocuments
	physical_legal_document = download_ujjwala_physical_legal_docs(pi_obj.parent)
	upload_url = upload_file_to_minio_bucket(
		physical_legal_document,
		"ujjwaladocuments",
		"ujjwala_{}_physical_legal_document".format(pi_obj.parent_id)
	)

	if PreInspectionDocuments.objects.filter(
		parent=pi_obj, type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT
	).count() > 1:
		PreInspectionDocuments.objects.filter(
			parent=pi_obj, type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT
		).delete()

	pi_doc_obj = PreInspectionDocuments.objects.get_or_create(
		parent=pi_obj, type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT
	)[0]
	pi_doc_obj.link = upload_url
	pi_doc_obj.save()

	pi_obj.parent.event_legal_documents_upload_channel_whatsapp()
	create_job_function = partial(
		django_rq.enqueue,
		"ujjwala.jobs.is_application_ready_for_disbursement",
		args=(pi_obj.parent.id,)
	)
	transaction.on_commit(create_job_function)


def preinspection_add_lead_to_vicidial(preinspection_id, process_instance_id):
	from ujjwala.models import PreInspection

	obj = PreInspection.objects.get(pk=preinspection_id)
	add_lead_to_vicidial_list(VICIDIAL_LIST, obj.parent.contact_mobile, obj.parent.name, obj.parent_id)

	res = requests.post(
		"http://192.168.168.3/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&custom_fields=Y&function=add_lead&phone_number={}&phone_code=1&list_id={}"
		"&first_name={}&last_name={}&process_instance_id={}".format(
			obj.parent.contact_mobile,
			VICIDIAL_LIST,
			obj.parent.name, obj.parent_id, process_instance_id)
	)
	res.raise_for_status()
	obj.parent.event_whatsapp_camunda_update_address(process_instance_id)
	return res.text


def preinspection_delete_lead_from_vicidial(preinspection_id, contact_mobile):
	return delete_lead_from_vicidial_list(VICIDIAL_LIST, contact_mobile)


def review_address_add_lead_to_vicidial(list_id, contact_mobile, name, application_id, process_instance_id):
	from ujjwala.models import UjjwalaV2Application

	application_obj = UjjwalaV2Application.objects.get(id=application_id)

	res = requests.post(
		"http://192.168.168.3/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&custom_fields=Y&function=add_lead&phone_number={}&phone_code=1&list_id={}"
		"&first_name={}&last_name={}&process_instance_id={}".format(
			contact_mobile,
			list_id,
			name, application_id, process_instance_id)
	)
	res.raise_for_status()
	application_obj.event_whatsapp_camunda_update_address(process_instance_id)
	return res.text


def review_address_delete_lead_from_vicidial(list_id, contact_mobile):
	return delete_lead_from_vicidial_list(list_id, contact_mobile)


def send_payment_profile_update_whatsapp_message(application_id, contact_mobile, camunda_process_id):
	from ujjwala.models import UjjwalaV2Application

	application = UjjwalaV2Application.objects.get(pk=application_id)
	time.sleep(3)
	application.event_whatsapp_update_bank_details_new()
	BankDetailsUpdateRequest.objects.create(parent=application, camunda_process_id=camunda_process_id)


def payment_profile_update_add_lead_to_vicidial(list_id, contact_mobile, name, application_id, process_instance_id):
	from ujjwala.models import UjjwalaV2Application

	application_obj = UjjwalaV2Application.objects.get(id=application_id)

	res = requests.post(
		"http://192.168.168.3/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&custom_fields=Y&function=add_lead&phone_number={}&phone_code=1&list_id={}"
		"&first_name={}&last_name={}&process_instance_id={}".format(
			contact_mobile,
			list_id,
			name, application_id, process_instance_id)
	)
	res.raise_for_status()
	# application_obj.event_whatsapp_camunda_update_address(process_instance_id)
	return res.text


def payment_profile_update_delete_lead_and_update_dca(list_id, contact_mobile, application_id):
	from ujjwala.models import UjjwalaV2Application

	application_obj = UjjwalaV2Application.objects.get(pk=application_id)
	variables = {
		"consumer_id": {"type": "String", "value": application_obj.consumer_id}
	}
	# application_obj.bank_account_number = bank_account_number
	# application_obj.ifsc_code = ifscode
	# application_obj.save()
	delete_lead_from_vicidial_list(list_id, contact_mobile)
	return variables


def payment_profile_update_sdms_status_in_dca(case_num):
	from connection_app.models import PaymentProfile
	from ujjwala.models import UjjwalaV2Application
	from connection_app.enums import PaymentProfileApprovalStatusEnum

	pp_obj = PaymentProfile.objects.get(case_num=case_num)
	pp_obj.approval_status = PaymentProfileApprovalStatusEnum.REJECTED
	pp_obj.save()

	application_obj: UjjwalaV2Application = UjjwalaV2Application.objects.get(
		consumer_id=pp_obj.relationship_id)
	variables = {
		"name": {"value": application_obj.name, "type": "String"},
		"contact_mobile": {"value": application_obj.contact_mobile, "type": "String"},
		"application_id": {"value": application_obj.id, "type": "String"},
		"action": {"value": "reject" if pp_obj.pfms_payment_method == 'NCTC' else 'accept'}
	}
	return variables


def review_address_update_in_dca(application_id, address_json, agent=''):
	from ujjwala.models import UjjwalaV2Application, ConnectionDisbursement
	from django_comments_xtd.models import XtdComment

	application = UjjwalaV2Application.objects.get(pk=application_id)

	if agent:
		comment = "Old Addr: {} Filled By Agent {}".format(json.dumps(application.address_json), agent)
	else:
		comment = "Old Addr: {}".format(json.dumps(application.address_json))

	XtdComment.objects.create(content_type=ContentType.objects.get(
		app_label='ujjwala', model='ujjwalav2application'
	), object_pk=application_id, site_id=1,	comment=comment)

	application.address_json = address_json
	if agent.lower() != 'self':
		application.address_verified = True
		application.address_verified_on = datetime.datetime.now()
		application.address_verified_by = agent
		application.save()

	ci_obj: ConnectionDisbursement = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
	if ci_obj.status in (
	ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED, ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW):
		ci_obj.documents.all().delete()
		ci_obj.status = ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING
		ci_obj.save()
	re_create_legal_docs(application)
	application.event_legal_documents_reupload_channel_whatsapp("Address Updated")


def review_address_update_in_dca_other_action(application_id, action, agent=''):
	from ujjwala.models import UjjwalaV2Application, PreInspection

	application = UjjwalaV2Application.objects.get(pk=application_id)
	if action == 'OUT_OF_SERVICE_AREA':
		application.transition_on_hold(description="Out Of Service Area")
		application.save()
	elif action == 'INVALID_LOCATION':
		pi_obj = PreInspection.objects.get(parent_id=application_id)
		rejected_reasons = [PreInspectionRejectionReasonsEnum.CONDITION_LOCATION_MISMATCH]
		pi_obj.pre_inspection_review(rejected_reasons=rejected_reasons)
		pi_obj.save()


def variables_to_update_for_preinspection(task):
	from ujjwala.models import PreInspection
	variables = {}

	preinspection_id = task.get_variable('preinspection_id')
	if preinspection_id:
		pi_obj = PreInspection.objects.get(pk=preinspection_id)

		kitchen_photo = task.get_variable('kitchen_photo')

		if kitchen_photo:
			variables["kitchen_photo"] = {"value": pi_obj.documents.get(type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO).link}

		main_gate_photo = task.get_variable('kitchen_photo')
		if main_gate_photo:
			variables["main_gate_photo"] = {"value": pi_obj.documents.get(type=UjjwalaApplicationDocumentsEnum.MAIN_GATE).link}
	return variables


def get_consumer_id_for_iocl_investigation(application_id):
	from ujjwala.models import UjjwalaV2Application

	application = UjjwalaV2Application.objects.get(pk=application_id)

	uf_self = application.family_members.get(relation='SELF')
	consumer_id: str = uf_self.uid_check_result.get('consumer_id')

	if consumer_id.startswith('372'):
		formatted_consumer_id = "72" + consumer_id[3:].rjust(14, '0')
	else:
		formatted_consumer_id = "72" + consumer_id[2:].rjust(14, '0')
	return formatted_consumer_id
