"""
Django Forms for Ujjwala V3 Public Application

This module provides forms for the public-facing Ujjwala V3 application submission.
"""

from django import forms
from .models import UjjwalaV3Application, UjjwalaV3Address, UjjwalaV3FamilyMember
from .enums import (
    Gender, Caste, FamilyDocumentType, LPGConnectionType,
    AddressType, RelationToApplicant, POACode
)


class UjjwalaV3ApplicationForm(forms.ModelForm):
    """Main application form for Ujjwala V3."""

    class Meta:
        model = UjjwalaV3Application
        fields = [
            # Applicant Details
            'applicant_full_name',
            'applicant_first_name',
            'applicant_middle_name',
            'applicant_last_name',
            'applicant_gender',
            'applicant_dob',
            'applicant_aadhaar_number',
            'applicant_mobile',
            'applicant_email',
            'caste',

            # Bank Details
            'bank_account_number',
            'bank_ifsc',
            'bank_name',
            'bank_branch',
            'bank_account_name',

            # Migration Details
            'is_migrant',

            # Family Document
            'family_doc_issuing_state',
            'family_doc_type',
            'family_doc_number',

            # LPG Connection
            'lpg_connection_type',
        ]
        widgets = {
            'applicant_full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name as per Aadhaar'
            }),
            'applicant_first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name'
            }),
            'applicant_middle_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Middle name (optional)'
            }),
            'applicant_last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name (optional)'
            }),
            'applicant_gender': forms.Select(attrs={'class': 'form-control'}),
            'applicant_dob': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'applicant_aadhaar_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '12-digit Aadhaar number'
            }),
            'applicant_mobile': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '10-digit mobile number'
            }),
            'applicant_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address (optional)'
            }),
            'caste': forms.Select(attrs={'class': 'form-control'}),
            'bank_account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank account number'
            }),
            'bank_ifsc': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'IFSC code (e.g., SBIN0001234)'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank name'
            }),
            'bank_branch': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Branch name'
            }),
            'bank_account_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account holder name'
            }),
            'is_migrant': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'family_doc_issuing_state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State name (e.g., Punjab)'
            }),
            'family_doc_type': forms.Select(attrs={'class': 'form-control'}),
            'family_doc_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Document number (optional)'
            }),
            'lpg_connection_type': forms.Select(attrs={'class': 'form-control'}),
        }


class UjjwalaV3AddressForm(forms.ModelForm):
    """Form for address entry (Current/Permanent)."""

    class Meta:
        model = UjjwalaV3Address
        fields = [
            'address_type',
            'house_flat_no',
            'floor_number',
            'building_colony',
            'street_road',
            'village_panchayat_area',
            'block_sub_district',
            'district',
            'city_town',
            'state',
            'pincode',
            'landmark',
            'poa_code',
        ]
        widgets = {
            'address_type': forms.Select(attrs={'class': 'form-control'}),
            'house_flat_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'House/Flat number'
            }),
            'floor_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Floor number (optional)'
            }),
            'building_colony': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Building/Colony name (optional)'
            }),
            'street_road': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Street/Road name (optional)'
            }),
            'village_panchayat_area': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Village/Panchayat/Area (optional)'
            }),
            'block_sub_district': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Block/Sub-district (optional)'
            }),
            'district': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'District'
            }),
            'city_town': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City/Town (e.g., Ludhiana)'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State (e.g., Punjab)'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '6-digit pincode'
            }),
            'landmark': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nearby landmark (optional)'
            }),
            'poa_code': forms.Select(attrs={'class': 'form-control'}),
        }


class UjjwalaV3FamilyMemberForm(forms.ModelForm):
    """Form for family member entry."""

    class Meta:
        model = UjjwalaV3FamilyMember
        fields = [
            'full_name',
            'relation_to_applicant',
            'gender',
            'dob',
            'aadhaar_number',
            'uid_front_link',
            'uid_back_link',
            'uid_original_front_link',
            'uid_original_back_link',
            'uid_check_result',
            'is_valid_uid',
            'validated',
            'uid_front_compressed',
            'uid_back_compressed',
            'uid_front_file_size',
            'uid_back_file_size',
            'additional_details',
            'ration_card_available',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name as per Aadhaar'
            }),
            'relation_to_applicant': forms.Select(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'dob': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'aadhaar_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '12-digit Aadhaar number'
            }),
            'uid_front_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'UID front photo URL'
            }),
            'uid_back_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'UID back photo URL'
            }),
            'uid_original_front_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Original front photo URL'
            }),
            'uid_original_back_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Original back photo URL'
            }),
            'uid_check_result': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'OCR result JSON'
            }),
            'is_valid_uid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'validated': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'uid_front_compressed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'uid_back_compressed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'uid_front_file_size': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1.2 MB'
            }),
            'uid_back_file_size': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1.5 MB'
            }),
            'additional_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional details JSON'
            }),
            'ration_card_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
