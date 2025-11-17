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
            'applicant_age',
            'applicant_aadhaar_number',
            'applicant_mobile_number',
            'applicant_alternate_mobile_number',
            'applicant_email',
            'caste',

            # Bank Details
            'bank_account_number',
            'bank_ifsc_code',
            'bank_name',
            'bank_branch_name',
            'account_holder_name',

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
            'applicant_age': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Age (must be 18+)'
            }),
            'applicant_aadhaar_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '12-digit Aadhaar number'
            }),
            'applicant_mobile_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '10-digit mobile number'
            }),
            'applicant_alternate_mobile_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Alternate mobile (optional)'
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
            'bank_ifsc_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'IFSC code (e.g., SBIN0001234)'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank name'
            }),
            'bank_branch_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Branch name'
            }),
            'account_holder_name': forms.TextInput(attrs={
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
            'house_number',
            'building_name',
            'floor_number',
            'street_road',
            'area_locality',
            'landmark',
            'village_town',
            'city',
            'state',
            'pincode',
            'poa_code',
        ]
        widgets = {
            'address_type': forms.Select(attrs={'class': 'form-control'}),
            'house_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'House/Flat number'
            }),
            'building_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Building name (optional)'
            }),
            'floor_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Floor number (optional)'
            }),
            'street_road': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Street/Road name (optional)'
            }),
            'area_locality': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Area/Locality'
            }),
            'landmark': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nearby landmark (optional)'
            }),
            'village_town': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Village/Town (optional)'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City (e.g., Ludhiana)'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State (e.g., Punjab)'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '6-digit pincode'
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
            'date_of_birth',
            'aadhaar_number',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name as per Aadhaar'
            }),
            'relation_to_applicant': forms.Select(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'aadhaar_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '12-digit Aadhaar number'
            }),
        }
