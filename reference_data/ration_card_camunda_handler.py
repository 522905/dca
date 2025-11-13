from camunda.external_task.external_task import ExternalTask, TaskResult
# reference_data/utils/ration_card_processor.py
import json
import requests
from typing import Dict, Any, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction
from reference_data.models import RationCard, RationCardFamilyMember

import logging

from ujjwala.models import UjjwalaV2Application

logger = logging.getLogger(__name__)
CAMUNDA_URL = "https://camunda.dca.arungas.com/engine-rest"


class RationCardProcessingError(Exception):
	"""Base exception for ration card processing errors"""
	pass


class RationCardMismatchError(RationCardProcessingError):
	"""Raised when ration_card variable doesn't match JSON RationNo"""
	pass


class DuplicateRationCardError(RationCardProcessingError):
	"""Raised when ration card already exists"""
	pass


class MissingRequiredVariableError(RationCardProcessingError):
	"""Raised when required variables are missing"""
	pass


def normalize_value(value: Any) -> Optional[Any]:
	"""Convert 'NULL' strings and empty values to None"""
	if value in ('NULL', 'null', '', '--', '---SELECT GAS CONSUMER---'):
		return None
	return value


def is_invalid_family_member(member: Dict) -> bool:
	"""Check if family member is a header or NULL row that should be filtered"""
	sr = str(member.get('Sr', '')).strip().upper()
	name = str(member.get('Name', '')).strip().upper()

	if sr == 'NULL' or name == 'NULL':
		return True

	if sr == 'SR.' or 'NAME OF THE FAMILY MEMBER' in name:
		return True

	return False


def download_file_from_camunda(camunda_url: str, process_instance_id: str, var_name: str) -> Optional[ContentFile]:
	"""Download FILE variable from Camunda"""
	try:
		url = f"{camunda_url}/process-instance/{process_instance_id}/variables/{var_name}/data"
		response = requests.get(url, stream=True, timeout=30)
		response.raise_for_status()

		file_content = b''
		for chunk in response.iter_content(chunk_size=8192):
			file_content += chunk

		# Get filename from content-disposition header
		filename = f"{process_instance_id}_{var_name}"
		if 'content-disposition' in response.headers:
			cd = response.headers['content-disposition']
			# Parse properly: filename="something.png"
			import re
			match = re.search(r'filename="?([^";\s]+)"?', cd)
			if match:
				filename = match.group(1)

		# Set default extension if missing
		if '.' not in filename:
			if var_name == 'screenshot_file':
				filename = f"{filename}.png"
			elif var_name == 'raw_html':
				filename = f"{filename}.html"

		return ContentFile(file_content, name=filename)

	except Exception as e:
		raise RationCardProcessingError(f"Failed to download file {var_name}: {str(e)}")


@transaction.atomic
def process_ration_card_task(
		variables: Dict[str, Any],
		camunda_url: str,
		process_instance_id: str
) -> RationCard:
	"""
	Process ration card Camunda task variables and save to database.

	Raises:
		RationCardMismatchError: If ration_card doesn't match JSON RationNo
		DuplicateRationCardError: If ration card already exists
		MissingRequiredVariableError: If required variables are missing
		RationCardProcessingError: For other processing errors
	"""

	# Extract required variables (corrected - no .get('value'))
	uid = variables.get('uid')
	ration_card_var = variables.get('ration_card')

	# Parse JSON payload
	payload_data = variables.get('payload')
	if not payload_data:
		raise RationCardProcessingError("Missing payload variable")

	try:
		payload = json.loads(payload_data)
	except (json.JSONDecodeError, TypeError) as e:
		raise RationCardProcessingError(f"Failed to parse JSON payload: {str(e)}")

	if payload.get('error') == 'Unable to fetch ration card details':
		raise Exception("Camunda payload indicates failure to fetch ration card details")

	# Extract and validate RationNo
	json_ration_no = payload.get('RationNo')
	if not json_ration_no:
		raise RationCardProcessingError("RationNo not found in JSON payload")

	if ration_card_var.strip() != json_ration_no.strip():
		raise RationCardMismatchError(
			f"ration_card '{ration_card_var}' does not match JSON RationNo '{json_ration_no}'"
		)

	# Check for duplicate
	if RationCard.objects.filter(ration_no=json_ration_no).exists():
		raise DuplicateRationCardError(f"RationCard with ration_no '{json_ration_no}' already exists")

	# Download screenshot_file if present
	screenshot_file = None
	if 'screenshot_file' in variables:
		screenshot_file = download_file_from_camunda(
			camunda_url,
			process_instance_id,
			'screenshot_file'
		)

	# Download raw_html if present
	raw_html_file = None
	if 'raw_html' in variables:
		raw_html_file = download_file_from_camunda(
			camunda_url,
			process_instance_id,
			'raw_html'
		)

	# Prepare raw variables (exclude FILE variables)
	raw_variables = {
		k: v for k, v in variables.items()
		if k not in ('screenshot_file', 'raw_html')
	}

	# Create RationCard
	ration_card = RationCard.objects.create(
		uid=uid,
		ration_no=json_ration_no,
		scheme=normalize_value(payload.get('Scheme')),
		conn_type=normalize_value(payload.get('ConnType')),
		gas_no=normalize_value(payload.get('GasNo')),
		gas_company=normalize_value(payload.get('GasCompany')),
		owner_name=normalize_value(payload.get('OwnerName')),
		gas_agency=normalize_value(payload.get('GasAgency')),
		head_of_family=normalize_value(payload.get('HeadOfFamily')),
		address=normalize_value(payload.get('Address')),
		annual_income=normalize_value(payload.get('AnnualIncome')),
		fps_no=normalize_value(payload.get('FPSNo')),
		fps_name_address=normalize_value(payload.get('FPSNameAddress')),
		raw_variables=raw_variables
	)

	# Save screenshot file
	if screenshot_file:
		ration_card.screenshot_file.save(
			screenshot_file.name,
			screenshot_file,
			save=True
		)

	# Save raw_html file
	if raw_html_file:
		ration_card.raw_html.save(
			raw_html_file.name,
			raw_html_file,
			save=True
		)

	# Process family members
	family_members = payload.get('FamilyMembers', [])
	for member in family_members:
		if is_invalid_family_member(member):
			continue

		RationCardFamilyMember.objects.create(
			ration_card=ration_card,
			sr=normalize_value(member.get('Sr')),
			name=normalize_value(member.get('Name')),
			aadhar=normalize_value(member.get('Aadhar')),
			sex=normalize_value(member.get('Sex')),
			age=normalize_value(member.get('Age'))
		)

	return ration_card


def cleanup_ration_card_tasks(task: ExternalTask):
	from ujjwala.models import FamilyMembers
	from reference_data.models import UIDNotHavingRationCard, RationCardFamilyMember, RationCard

	ration_card = task.get_variable('ration_card')
	uid = task.get_variable('uid')

	fm_obj = FamilyMembers.objects.filter(uid_no=uid).first()

	if not fm_obj:
		raise Exception("No Family Member Found")

	if ration_card == 'False':
		fm_obj.ration_card_available = False
		unhrc = UIDNotHavingRationCard.objects.create(uid=uid, auto_checked=True)
		unhrc.mapped = True
		unhrc.save()
	else:
		rc_obj: RationCard = RationCard.objects.filter(uid=uid).first()
		fm_obj.ration_card_available = True
		rc_obj.content_type = ContentType.objects.get_for_model(FamilyMembers)
		rc_obj.object_id = fm_obj.id
		rc_obj.save()

	fm_obj.save()

	return True

def handle_ration_card_process_details(task: ExternalTask) -> TaskResult:
	"""Handler for RATION_CARD#PROCESS_DETAILS topic"""
	process_instance_id = task.get_process_instance_id()

	try:
		logger.info(f"Processing ration card for instance: {process_instance_id}")

		if task.get_variable('ration_card') == 'False':
			return task.complete()

		ration_card = process_ration_card_task(
			variables=task.get_variables(),
			camunda_url=CAMUNDA_URL,
			process_instance_id=process_instance_id
		)

		logger.info(f"Successfully processed RationCard: {ration_card.ration_no}")
		return task.complete()

	except RationCardMismatchError as e:
		logger.error(f"Mismatch error: {str(e)}")
		return task.bpmn_error(
			error_code="RATION_CARD_MISMATCH",
			error_message=str(e)
		)

	except DuplicateRationCardError as e:
		logger.error(f"Duplicate error: {str(e)}")
		return task.bpmn_error(
			error_code="DUPLICATE_RATION_CARD",
			error_message=str(e)
		)

	except MissingRequiredVariableError as e:
		logger.error(f"Missing variable: {str(e)}")
		return task.bpmn_error(
			error_code="MISSING_VARIABLE",
			error_message=str(e)
		)

	except RationCardProcessingError as e:
		logger.error(f"Processing error: {str(e)}")
		return task.failure(
			error_message=str(e),
			error_details=str(e),
			max_retries=3,
			retry_timeout=5000
		)

	except Exception as e:
		logger.exception(f"Unexpected error: {str(e)}")
		return task.failure(
			error_message="Unexpected error occurred",
			error_details=str(e),
			max_retries=3,
			retry_timeout=5000
		)
