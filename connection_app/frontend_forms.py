import datetime
import json
from dal import autocomplete
from django import forms, apps
from django.core.exceptions import ValidationError
from django.forms import NumberInput
from django_currentuser.middleware import get_current_user
from datetime import timedelta
from django.utils import timezone

from connection_app.enums import ConnectionApplicationProcessType, ConnectionApplicationLeadStatus, \
        ConnectionApplicationDocumentsEnum, HouseTypeEnum, PostInspectionActivityTypeEnum, PostInspectionStatusEnum, \
        TemplateEnum, ProofTypeEnum

from .models import OmcConversionRequest


from hashicorp import hashicorp_client
from inactive_customers.models import InactiveCustomer
from reference_data.models import ServiceType, Product, SDMSServiceRequest
from teams.models import SDMSServiceArea, UserProfile, SDMSUser


class OmcCylinderConversionForm(forms.ModelForm):
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Overriding choices for the omc_type field
		self.fields['omc_type'].choices = [('HPCL', 'HPCL', 'IOCL'), ('BPCL', 'BPCL', 'IOCL')]
		self.fields['cylinder_type'].choices = [('14.2KG', '19KG, 5KG, 5KG_FTL'), ('14.2KG', '19KG', '5KG_FTL')]

	def clean_contact_mobile(self):
		mobile = self.cleaned_data.get('contact_mobile')
		if not mobile:
			return mobile

		fifteen_days_ago = timezone.now() - timedelta(days=15)

		recent_request = OmcConversionRequest.objects.filter(
			contact_mobile=mobile,
			created_on__gte=fifteen_days_ago
		).exists()

		if recent_request:
			raise ValidationError("A request with this mobile number was already submitted in the last 15 days.")

		return mobile


	class Meta:
		model = OmcConversionRequest
		fields = ['contact_mobile', 'customer_name', 'area', 'omc_type', 'omc_cylinder_photo_after', 'consumer_id', 'dac_code', 'cylinder_type']
