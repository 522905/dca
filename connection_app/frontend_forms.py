import datetime
import json
from dal import autocomplete
from django import forms, apps
from django.core.exceptions import ValidationError
from django.forms import NumberInput
from django_currentuser.middleware import get_current_user

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
		# Overriding choices for the cylinder_type field
		self.fields['cylinder_type'].choices = [('14.2Kg', '14.2Kg'), ('5Kg', '5Kg')]

	class Meta:
		model = OmcConversionRequest
		fields = ['contact_mobile', 'customer_name', 'area', 'cylinder_type', 'omc_cylinder_photo_before', 'omc_cylinder_photo_after']
