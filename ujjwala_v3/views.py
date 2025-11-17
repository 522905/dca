"""
Views for Ujjwala V3 Public Application Form

This module provides views for the public-facing application submission.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
import json

from .models import (
    UjjwalaV3Application, UjjwalaV3Address, UjjwalaV3FamilyMember,
    UjjwalaV3Document
)
from .forms import UjjwalaV3ApplicationForm, UjjwalaV3AddressForm, UjjwalaV3FamilyMemberForm
from .enums import AddressType, DocumentType


def public_application_form(request):
    """Display the public application form."""
    context = {
        'application_form': UjjwalaV3ApplicationForm(),
        'address_form': UjjwalaV3AddressForm(),
        'family_member_form': UjjwalaV3FamilyMemberForm(),
    }
    return render(request, 'ujjwala_v3/public_form.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def submit_public_application(request):
    """Handle the public application form submission via AJAX."""
    try:
        data = json.loads(request.body)

        with transaction.atomic():
            # Create the main application
            application_data = data.get('application', {})
            application = UjjwalaV3Application.objects.create(
                # Applicant Details
                applicant_full_name=application_data.get('applicant_full_name'),
                applicant_first_name=application_data.get('applicant_first_name'),
                applicant_middle_name=application_data.get('applicant_middle_name', ''),
                applicant_last_name=application_data.get('applicant_last_name', ''),
                applicant_gender=application_data.get('applicant_gender'),
                applicant_dob=application_data.get('applicant_dob'),
                applicant_age=application_data.get('applicant_age'),
                applicant_aadhaar_number=application_data.get('applicant_aadhaar_number'),
                applicant_mobile_number=application_data.get('applicant_mobile_number'),
                applicant_alternate_mobile_number=application_data.get('applicant_alternate_mobile_number', ''),
                applicant_email=application_data.get('applicant_email', ''),
                caste=application_data.get('caste'),

                # Bank Details
                bank_account_number=application_data.get('bank_account_number'),
                bank_ifsc_code=application_data.get('bank_ifsc_code'),
                bank_name=application_data.get('bank_name'),
                bank_branch_name=application_data.get('bank_branch_name'),
                account_holder_name=application_data.get('account_holder_name'),

                # Migration
                is_migrant=True,  # Always true for V3

                # Family Document
                family_doc_issuing_state=application_data.get('family_doc_issuing_state'),
                family_doc_type=application_data.get('family_doc_type'),
                family_doc_number=application_data.get('family_doc_number', ''),

                # LPG Connection
                lpg_connection_type=application_data.get('lpg_connection_type'),
            )

            # Create addresses
            addresses = data.get('addresses', [])
            for addr_data in addresses:
                UjjwalaV3Address.objects.create(
                    application=application,
                    address_type=addr_data.get('address_type'),
                    house_number=addr_data.get('house_number'),
                    building_name=addr_data.get('building_name', ''),
                    floor_number=addr_data.get('floor_number', ''),
                    street_road=addr_data.get('street_road', ''),
                    area_locality=addr_data.get('area_locality'),
                    landmark=addr_data.get('landmark', ''),
                    village_town=addr_data.get('village_town', ''),
                    city=addr_data.get('city'),
                    state=addr_data.get('state'),
                    pincode=addr_data.get('pincode'),
                    poa_code=addr_data.get('poa_code'),
                )

            # Create family members
            family_members = data.get('family_members', [])
            for member_data in family_members:
                UjjwalaV3FamilyMember.objects.create(
                    application=application,
                    full_name=member_data.get('full_name'),
                    relation_to_applicant=member_data.get('relation_to_applicant'),
                    gender=member_data.get('gender'),
                    date_of_birth=member_data.get('date_of_birth'),
                    aadhaar_number=member_data.get('aadhaar_number'),
                )

            # Create documents
            documents = data.get('documents', [])
            for doc_data in documents:
                UjjwalaV3Document.objects.create(
                    application=application,
                    doc_type=doc_data.get('doc_type'),
                    file_url=doc_data.get('file_url'),
                    file_name=doc_data.get('file_name'),
                    file_size=doc_data.get('file_size'),
                    mime_type=doc_data.get('mime_type'),
                    description=doc_data.get('description', ''),
                )

            return JsonResponse({
                'success': True,
                'message': 'Application submitted successfully!',
                'application_id': str(application.id),
                'application_number': application.application_number or 'Will be generated upon submission'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error submitting application: {str(e)}'
        }, status=400)


def application_success(request, application_id):
    """Display success page after application submission."""
    try:
        application = UjjwalaV3Application.objects.get(id=application_id)
        context = {
            'application': application,
        }
        return render(request, 'ujjwala_v3/success.html', context)
    except UjjwalaV3Application.DoesNotExist:
        return render(request, 'ujjwala_v3/error.html', {
            'message': 'Application not found'
        })
