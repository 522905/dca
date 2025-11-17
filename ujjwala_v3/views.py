"""
Views for Ujjwala V3 Public Application Form

This module contains views for the public-facing application form.
"""

import os
import uuid
from datetime import datetime, date
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from minio import Minio
from minio.error import S3Error

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


def upload_to_minio(file, bucket_name, object_name):
    """
    Upload file to MinIO storage.

    Args:
        file: The uploaded file object
        bucket_name: Name of the MinIO bucket
        object_name: Name to give the object in MinIO

    Returns:
        str: Public URL of the uploaded file, or None if upload failed
    """
    try:
        # Initialize MinIO client
        minio_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_CREDENTIAL['access_key'],
            secret_key=settings.MINIO_CREDENTIAL['secret_key'],
            secure=True
        )

        # Check if bucket exists, create if not
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        # Upload file
        file.seek(0)  # Reset file pointer
        minio_client.put_object(
            bucket_name,
            object_name,
            file,
            length=file.size,
            content_type=file.content_type
        )

        # Return public URL
        public_url = f"{settings.MINIO_PUBLIC_URL}/{bucket_name}/{object_name}"
        return public_url

    except S3Error as e:
        print(f"MinIO upload error: {e}")
        return None
    except Exception as e:
        print(f"Upload error: {e}")
        return None


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

        # Validate gender (should be Female for PMUY V3)
        if applicant_gender != Gender.FEMALE:
            messages.warning(request, 'Note: PMUY V3 is primarily for female applicants. Your application will be reviewed.')

        # Get address details
        current_state = request.POST.get('current_state')
        permanent_state = request.POST.get('permanent_state')

        # Validate that states are different for migrants
        if current_state == permanent_state:
            messages.error(request, 'For migrant applications, Current and Permanent addresses must be in different states.')
            return render(request, 'ujjwala_v3/application_form.html')

        # Check if Aadhaar already exists
        if UjjwalaV3Application.objects.filter(applicant_aadhaar_number=applicant_aadhaar).exists():
            messages.error(request, 'An application with this Aadhaar number already exists.')
            return render(request, 'ujjwala_v3/application_form.html')

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

        if family_member_count == 0:
            messages.warning(request, 'No family members were added. Please add at least yourself as a family member.')

        # Upload documents
        bucket_name = settings.MINIO_UJJWALA_BUCKET_NAME
        documents_uploaded = []

        # Document mapping: form field name -> (DocumentType, description, is_required)
        document_mapping = {
            'aadhaar_front': (DocumentType.AADHAAR_FRONT, 'Aadhaar Card Front', True),
            'aadhaar_back': (DocumentType.AADHAAR_BACK, 'Aadhaar Card Back', True),
            'current_address_poa': (DocumentType.CURRENT_ADDRESS_POA, 'Current Address Proof', True),
            'permanent_address_poa': (DocumentType.PERMANENT_ADDRESS_POA, 'Permanent Address Proof', True),
            'bank_proof': (DocumentType.BANK_PROOF, 'Bank Proof Document', True),
            'applicant_photo': (DocumentType.APPLICANT_PHOTO, 'Applicant Photograph', True),
            'family_photo': (DocumentType.FAMILY_PHOTO, 'Family Photograph', True),
            'applicant_signature': (DocumentType.APPLICANT_SIGNATURE, 'Applicant Signature', True),
            'caste_certificate': (DocumentType.CASTE_CERTIFICATE, 'Caste Certificate', False),
            'kitchen_photo': (DocumentType.KITCHEN_PHOTO, 'Kitchen Photograph', False),
            'lpg_installation_area_photo': (DocumentType.LPG_INSTALLATION_AREA_PHOTO, 'LPG Installation Area Photo', False),
        }

        for field_name, (doc_type, description, is_required) in document_mapping.items():
            file = request.FILES.get(field_name)

            if file:
                # Generate unique filename
                file_ext = os.path.splitext(file.name)[1]
                object_name = f"ujjwala_v3/{application.application_number}/{doc_type.value}/{uuid.uuid4()}{file_ext}"

                # Upload to MinIO
                file_url = upload_to_minio(file, bucket_name, object_name)

                if file_url:
                    # Determine address relationship for POA documents
                    address = None
                    if doc_type == DocumentType.CURRENT_ADDRESS_POA:
                        address = current_address
                    elif doc_type == DocumentType.PERMANENT_ADDRESS_POA:
                        address = permanent_address

                    # Create document record
                    UjjwalaV3Document.objects.create(
                        application=application,
                        address=address,
                        doc_type=doc_type,
                        file_url=file_url,
                        file_name=file.name,
                        file_size=file.size,
                        mime_type=file.content_type,
                        description=description
                    )
                    documents_uploaded.append(description)
                else:
                    if is_required:
                        messages.warning(request, f'Failed to upload {description}. Please contact support.')
            elif is_required:
                messages.warning(request, f'{description} is required but was not uploaded.')

        # Success message
        messages.success(
            request,
            f'Your application has been submitted successfully! '
            f'Your application number is: {application.application_number}. '
            f'Please save this number for future reference.'
        )

        # Redirect to success page or show form again
        return redirect('ujjwala_v3_application_success', application_number=application.application_number)

    except Exception as e:
        print(f"Error creating application: {e}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'An error occurred while submitting your application: {str(e)}. Please try again.')
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
        return render(request, 'ujjwala_v3/application_success.html', {
            'application': application
        })
    except UjjwalaV3Application.DoesNotExist:
        messages.error(request, 'Application not found.')
        return redirect('ujjwala_v3_public_form')
