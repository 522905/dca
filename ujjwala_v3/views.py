"""
Views for Ujjwala V3 Public Application Form

This module contains views for the public-facing application form.
"""

from datetime import datetime, date
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import traceback
import sys

from .models import (
    UjjwalaV3Application,
    UjjwalaV3Address,
    UjjwalaV3FamilyMember,
    UjjwalaV3Document
)
from .enums import (
    Gender,
    Caste,
    AddressType,
    RelationToApplicant,
    LPGConnectionType,
    DocumentType,
    ApplicationStatus
)


def calculate_age(birth_date):
    """Calculate age from birth date."""
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age


@require_http_methods(["GET", "POST"])
def public_application_form(request):
    """
    Public application form view for Ujjwala V3.

    GET: Display the application form
    POST: Process form submission and create application
    """

    if request.method == "GET":
        return render(request, 'ujjwala_v3/application_form.html')

    # POST request - process form submission
    try:
        # Get applicant details
        applicant_first_name = request.POST.get('applicant_first_name', '').strip()
        applicant_middle_name = request.POST.get('applicant_middle_name', '').strip()
        applicant_last_name = request.POST.get('applicant_last_name', '').strip()

        # Construct full name
        name_parts = [applicant_first_name, applicant_middle_name, applicant_last_name]
        applicant_full_name = ' '.join([part for part in name_parts if part])

        applicant_gender = request.POST.get('applicant_gender')
        applicant_dob_str = request.POST.get('applicant_dob')
        applicant_dob = datetime.strptime(applicant_dob_str, '%Y-%m-%d').date()
        applicant_aadhaar = request.POST.get('applicant_aadhaar_number', '').strip()
        applicant_mobile = request.POST.get('applicant_mobile', '').strip()
        applicant_email = request.POST.get('applicant_email', '').strip()
        caste = request.POST.get('caste')

        # Validate age (must be 18+)
        age = calculate_age(applicant_dob)
        if age < 18:
            messages.error(request, 'Applicant must be at least 18 years old.')
            return render(request, 'ujjwala_v3/application_form.html')

        # Get address details
        current_state = request.POST.get('current_state')
        permanent_state = request.POST.get('permanent_state')

        # Validate that states are different for migrants
        if current_state == permanent_state:
            messages.error(request, 'For migrant applications, Current and Permanent addresses must be in different states.')
            return render(request, 'ujjwala_v3/application_form.html')

        # Check if Aadhaar already exists
        if UjjwalaV3Application.objects.filter(applicant_aadhaar_number=applicant_aadhaar).exists():
            error_msg = 'An application with this Aadhaar number already exists.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
            messages.error(request, error_msg)
            return render(request, 'ujjwala_v3/application_form.html')

        # Store filled_by information if user is authenticated
        filled_by_name = None
        filled_by_email = None
        if request.user.is_authenticated:
            filled_by_name = request.user.get_full_name() or request.user.username
            filled_by_email = request.user.email

        # Create application
        application = UjjwalaV3Application.objects.create(
            applicant_full_name=applicant_full_name,
            applicant_first_name=applicant_first_name,
            applicant_middle_name=applicant_middle_name or None,
            applicant_last_name=applicant_last_name or None,
            applicant_gender=applicant_gender,
            applicant_dob=applicant_dob,
            applicant_aadhaar_number=applicant_aadhaar,
            applicant_mobile=applicant_mobile,
            applicant_email=applicant_email or None,
            caste=caste,
            is_migrant=True,
            bank_account_name=request.POST.get('bank_account_name', '').strip(),
            bank_name=request.POST.get('bank_name', '').strip(),
            bank_branch=request.POST.get('bank_branch', '').strip(),
            bank_ifsc=request.POST.get('bank_ifsc', '').strip().upper(),
            bank_account_number=request.POST.get('bank_account_number', '').strip(),
            lpg_connection_type=request.POST.get('lpg_connection_type'),
            family_doc_issuing_state=request.POST.get('family_doc_issuing_state', '').strip() or None,
            family_doc_type=request.POST.get('family_doc_type') or None,
            family_doc_number=request.POST.get('family_doc_number', '').strip() or None,
            is_deprivation_decl_signed=request.POST.get('is_deprivation_decl_signed') == 'on',
            status=ApplicationStatus.DRAFT
        )

        # Create Current Address
        current_address = UjjwalaV3Address.objects.create(
            application=application,
            address_type=AddressType.CURRENT,
            house_flat_no=request.POST.get('current_house_flat_no', '').strip(),
            floor_number=request.POST.get('current_floor_number', '').strip() or None,
            building_colony=request.POST.get('current_building_colony', '').strip() or None,
            street_road=request.POST.get('current_street_road', '').strip() or None,
            village_panchayat_area=request.POST.get('current_village_panchayat_area', '').strip() or None,
            block_sub_district=request.POST.get('current_block_sub_district', '').strip() or None,
            district=request.POST.get('current_district', '').strip(),
            city_town=request.POST.get('current_city_town', '').strip(),
            state=current_state,
            pincode=request.POST.get('current_pincode', '').strip(),
            landmark=request.POST.get('current_landmark', '').strip() or None,
            poa_code=request.POST.get('current_poa_code')
        )

        # Create Permanent Address
        permanent_address = UjjwalaV3Address.objects.create(
            application=application,
            address_type=AddressType.PERMANENT,
            house_flat_no=request.POST.get('permanent_house_flat_no', '').strip(),
            floor_number=request.POST.get('permanent_floor_number', '').strip() or None,
            building_colony=request.POST.get('permanent_building_colony', '').strip() or None,
            street_road=request.POST.get('permanent_street_road', '').strip() or None,
            village_panchayat_area=request.POST.get('permanent_village_panchayat_area', '').strip() or None,
            block_sub_district=request.POST.get('permanent_block_sub_district', '').strip() or None,
            district=request.POST.get('permanent_district', '').strip(),
            city_town=request.POST.get('permanent_city_town', '').strip(),
            state=permanent_state,
            pincode=request.POST.get('permanent_pincode', '').strip(),
            landmark=request.POST.get('permanent_landmark', '').strip() or None,
            poa_code=request.POST.get('permanent_poa_code')
        )

        # Create Family Members
        family_member_count = 0
        for key in request.POST.keys():
            if key.startswith('family_member_') and key.endswith('_name'):
                member_id = key.split('_')[2]

                member_name = request.POST.get(f'family_member_{member_id}_name', '').strip()
                member_relation = request.POST.get(f'family_member_{member_id}_relation')
                member_gender = request.POST.get(f'family_member_{member_id}_gender')
                member_dob_str = request.POST.get(f'family_member_{member_id}_dob')
                member_aadhaar = request.POST.get(f'family_member_{member_id}_aadhaar', '').strip()

                if member_name and member_relation and member_gender and member_dob_str and member_aadhaar:
                    member_dob = datetime.strptime(member_dob_str, '%Y-%m-%d').date()

                    UjjwalaV3FamilyMember.objects.create(
                        application=application,
                        full_name=member_name,
                        relation_to_applicant=member_relation,
                        gender=member_gender,
                        dob=member_dob,
                        aadhaar_number=member_aadhaar
                    )
                    family_member_count += 1

        # Process Aadhaar documents from TUS URLs
        uid_front_url = request.POST.get('uid_front_url')
        uid_back_url = request.POST.get('uid_back_url')

        if uid_front_url:
            UjjwalaV3Document.objects.create(
                application=application,
                doc_type=DocumentType.AADHAAR_FRONT,
                file_url=uid_front_url,
                file_name='aadhaar_front.jpg',
                description='Aadhaar Card Front (OCR Processed)'
            )

        if uid_back_url:
            UjjwalaV3Document.objects.create(
                application=application,
                doc_type=DocumentType.AADHAAR_BACK,
                file_url=uid_back_url,
                file_name='aadhaar_back.jpg',
                description='Aadhaar Card Back (OCR Processed)'
            )

        # Process dynamically uploaded documents
        documents_uploaded = []
        for key in request.POST.keys():
            if key.startswith('document_') and key.endswith('_type'):
                doc_id = key.split('_')[1]

                doc_type = request.POST.get(f'document_{doc_id}_type')
                doc_url = request.POST.get(f'document_{doc_id}_url')
                doc_filename = request.POST.get(f'document_{doc_id}_filename', 'uploaded_document')

                if doc_type and doc_url:
                    # Determine address relationship for POA documents
                    address = None
                    if doc_type == 'CURRENT_ADDRESS_POA':
                        address = current_address
                    elif doc_type == 'PERMANENT_ADDRESS_POA':
                        address = permanent_address

                    # Map document type string to DocumentType enum
                    try:
                        doc_type_enum = getattr(DocumentType, doc_type)

                        UjjwalaV3Document.objects.create(
                            application=application,
                            address=address,
                            doc_type=doc_type_enum,
                            file_url=doc_url,
                            file_name=doc_filename,
                            description=f'{doc_type} - {doc_filename}'
                        )
                        documents_uploaded.append(doc_type)
                    except AttributeError:
                        print(f"Invalid document type: {doc_type}")
                        continue

        # Success - check if AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return JSON response for AJAX
            return JsonResponse({
                'status': 'success',
                'application_number': application.application_number,
                'redirect_url': f'/ujjwala_v3/success/{application.application_number}/',
                'message': 'Application submitted successfully!'
            })
        else:
            # Regular form submission - redirect to success page
            messages.success(
                request,
                f'Your application has been submitted successfully! '
                f'Application Number: {application.application_number}. '
                f'Please save this number for future reference.'
            )
            return redirect('ujjwala_v3_application_success', application_number=application.application_number)

    except Exception as e:
        # Get detailed error information
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        error_traceback = ''.join(tb_lines)

        # Log error
        print(f"Error creating application: {e}")
        print(error_traceback)

        # Prepare error message
        error_msg = f'An error occurred while submitting your application: {str(e)}'

        # Check if AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return detailed JSON error for AJAX
            return JsonResponse({
                'status': 'error',
                'message': error_msg,
                'error': str(e),
                'error_type': exc_type.__name__ if exc_type else 'Unknown',
                'traceback': error_traceback
            }, status=500)
        else:
            # Regular form submission
            messages.error(request, error_msg)
            return render(request, 'ujjwala_v3/application_form.html')


@require_http_methods(["GET"])
def application_success(request, application_number):
    """
    Success page after application submission.

    Args:
        application_number: The application number to display
    """
    try:
        application = UjjwalaV3Application.objects.get(application_number=application_number)

        # Prepare filled_by information
        filled_by_info = None
        if request.user.is_authenticated:
            filled_by_info = {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email,
                'username': request.user.username
            }

        return render(request, 'ujjwala_v3/application_success.html', {
            'application': application,
            'filled_by': filled_by_info
        })
    except UjjwalaV3Application.DoesNotExist:
        messages.error(request, 'Application not found.')
        return redirect('ujjwala_v3_public_form')
