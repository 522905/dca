"""
Django REST Framework Serializers for Ujjwala V3 Application

This module provides comprehensive serializers for all Ujjwala V3 models,
supporting CRUD operations via REST API.
"""

from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model

from .models import (
    UjjwalaV3Application,
    UjjwalaV3Address,
    UjjwalaV3FamilyMember,
    UjjwalaV3Document,
    UjjwalaV3AuditLog
)
from .enums import (
    Gender, Caste, ApplicationStatus, AddressType,
    RelationToApplicant, DocumentType
)

User = get_user_model()


class UjjwalaV3AddressSerializer(serializers.ModelSerializer):
    """Serializer for Address model."""

    state_display = serializers.CharField(source='get_state_display', read_only=True)
    address_type_display = serializers.CharField(source='get_address_type_display', read_only=True)
    poa_code_display = serializers.CharField(source='get_poa_code_display', read_only=True)
    full_address = serializers.SerializerMethodField()

    class Meta:
        model = UjjwalaV3Address
        fields = [
            'id', 'application', 'address_type', 'address_type_display',
            'house_flat_no', 'floor_number', 'building_colony', 'street_road',
            'village_panchayat_area', 'block_sub_district', 'district',
            'city_town', 'state', 'state_display', 'pincode', 'landmark',
            'area_post_office_name', 'poa_code', 'poa_code_display',
            'latitude', 'longitude', 'full_address', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'full_address']

    def get_full_address(self, obj):
        """Return formatted full address."""
        return obj.get_full_address()

    def validate(self, data):
        """Custom validation."""
        # Ensure only one address per type per application
        if self.instance is None:  # Creating new
            application = data.get('application')
            address_type = data.get('address_type')

            if application and address_type:
                existing = UjjwalaV3Address.objects.filter(
                    application=application,
                    address_type=address_type
                ).exists()

                if existing:
                    raise serializers.ValidationError({
                        'address_type': f'Application already has a {address_type} address.'
                    })

        return data


class UjjwalaV3FamilyMemberSerializer(serializers.ModelSerializer):
    """Serializer for Family Member model."""

    relation_display = serializers.CharField(source='get_relation_to_applicant_display', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)
    age = serializers.SerializerMethodField()

    class Meta:
        model = UjjwalaV3FamilyMember
        fields = [
            'id', 'application', 'full_name', 'relation_to_applicant', 'relation_display',
            'gender', 'gender_display', 'aadhaar_number', 'dob', 'age',
            'age_at_application', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'age_at_application', 'created_at', 'updated_at', 'age']

    def get_age(self, obj):
        """Calculate current age."""
        from datetime import date
        if obj.dob:
            today = date.today()
            return today.year - obj.dob.year - ((today.month, today.day) < (obj.dob.month, obj.dob.day))
        return None

    def validate_dob(self, value):
        """Validate that DOB is provided and is not in the future."""
        if not value:
            raise serializers.ValidationError('Date of birth is required for all family members.')

        from datetime import date
        if value > date.today():
            raise serializers.ValidationError('Date of birth cannot be in the future.')

        return value

    def validate(self, data):
        """Custom validation."""
        # SELF member must match applicant details
        if data.get('relation_to_applicant') == RelationToApplicant.SELF:
            application = data.get('application') or (self.instance.application if self.instance else None)

            if application:
                if data.get('aadhaar_number') != application.applicant_aadhaar_number:
                    raise serializers.ValidationError({
                        'aadhaar_number': 'SELF member Aadhaar must match applicant Aadhaar.'
                    })
                if data.get('gender') != application.applicant_gender:
                    raise serializers.ValidationError({
                        'gender': 'SELF member gender must match applicant gender.'
                    })
                if data.get('dob') != application.applicant_dob:
                    raise serializers.ValidationError({
                        'dob': 'SELF member DOB must match applicant DOB.'
                    })

        return data


class UjjwalaV3DocumentSerializer(serializers.ModelSerializer):
    """Serializer for Document model."""

    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = UjjwalaV3Document
        fields = [
            'id', 'application', 'family_member', 'address', 'doc_type', 'doc_type_display',
            'file', 'file_url', 'file_name', 'file_size', 'mime_type', 'description',
            'uploaded_by', 'uploaded_by_name', 'is_verified', 'verified_by',
            'verified_by_name', 'verified_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'file_size', 'uploaded_by', 'verified_by', 'verified_at',
            'created_at', 'updated_at', 'file_url'
        ]

    def get_file_url(self, obj):
        """Get file URL."""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def validate(self, data):
        """Custom validation."""
        doc_type = data.get('doc_type')

        # Aadhaar documents must have family_member
        if doc_type in [DocumentType.AADHAAR_FRONT, DocumentType.AADHAAR_BACK]:
            if not data.get('family_member'):
                raise serializers.ValidationError({
                    'family_member': f'{doc_type} must be linked to a family member.'
                })

        # Address POA documents must have address
        if doc_type in [DocumentType.CURRENT_ADDRESS_POA, DocumentType.PERMANENT_ADDRESS_POA]:
            if not data.get('address'):
                raise serializers.ValidationError({
                    'address': f'{doc_type} must be linked to an address.'
                })

            # Validate address type matches
            address = data.get('address')
            if address:
                if doc_type == DocumentType.CURRENT_ADDRESS_POA and address.address_type != AddressType.CURRENT:
                    raise serializers.ValidationError({
                        'address': 'Current address POA must be linked to CURRENT address.'
                    })
                if doc_type == DocumentType.PERMANENT_ADDRESS_POA and address.address_type != AddressType.PERMANENT:
                    raise serializers.ValidationError({
                        'address': 'Permanent address POA must be linked to PERMANENT address.'
                    })

        return data


class UjjwalaV3AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for Audit Log model."""

    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)

    class Meta:
        model = UjjwalaV3AuditLog
        fields = [
            'id', 'application', 'action', 'actor', 'actor_name',
            'changes', 'remarks', 'ip_address', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class UjjwalaV3ApplicationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    caste_display = serializers.CharField(source='get_caste_display', read_only=True)
    lpg_connection_type_display = serializers.CharField(source='get_lpg_connection_type_display', read_only=True)
    applicant_age = serializers.IntegerField(read_only=True)
    current_address = serializers.SerializerMethodField()

    class Meta:
        model = UjjwalaV3Application
        fields = [
            'id', 'application_number', 'applicant_full_name', 'applicant_mobile',
            'applicant_email', 'applicant_age', 'caste', 'caste_display',
            'lpg_connection_type', 'lpg_connection_type_display',
            'status', 'status_display', 'submitted_at', 'created_at', 'updated_at',
            'current_address'
        ]
        read_only_fields = ['id', 'application_number', 'created_at', 'updated_at']

    def get_current_address(self, obj):
        """Get current address city and state."""
        current = obj.get_current_address()
        if current:
            return {
                'city_town': current.city_town,
                'state': current.get_state_display(),
                'district': current.district
            }
        return None


class UjjwalaV3ApplicationDetailSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for detail views."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    gender_display = serializers.CharField(source='get_applicant_gender_display', read_only=True)
    caste_display = serializers.CharField(source='get_caste_display', read_only=True)
    lpg_connection_type_display = serializers.CharField(source='get_lpg_connection_type_display', read_only=True)
    family_doc_type_display = serializers.CharField(source='get_family_doc_type_display', read_only=True)
    family_doc_issuing_state_display = serializers.CharField(source='get_family_doc_issuing_state_display', read_only=True)

    # Nested relationships
    addresses = UjjwalaV3AddressSerializer(many=True, read_only=True)
    family_members = UjjwalaV3FamilyMemberSerializer(many=True, read_only=True)
    documents = UjjwalaV3DocumentSerializer(many=True, read_only=True)

    # Computed fields
    applicant_age = serializers.IntegerField(read_only=True)
    is_complete = serializers.BooleanField(read_only=True)
    is_migrant_verified = serializers.SerializerMethodField()

    # User details
    submitted_by_name = serializers.CharField(source='submitted_by.get_full_name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)

    class Meta:
        model = UjjwalaV3Application
        fields = '__all__'
        read_only_fields = [
            'id', 'application_number', 'submitted_at', 'verified_at',
            'approved_at', 'connection_issued_at', 'created_at', 'updated_at',
            'submitted_by', 'verified_by', 'approved_by'
        ]

    def get_is_migrant_verified(self, obj):
        """Check if migration status is verified."""
        return obj.is_migrant_verified()


class UjjwalaV3ApplicationCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating applications with nested data."""

    # Nested write support
    addresses = UjjwalaV3AddressSerializer(many=True, required=False)
    family_members = UjjwalaV3FamilyMemberSerializer(many=True, required=False)

    class Meta:
        model = UjjwalaV3Application
        exclude = [
            'submitted_at', 'verified_at', 'approved_at', 'connection_issued_at',
            'submitted_by', 'verified_by', 'approved_by'
        ]
        read_only_fields = ['id', 'application_number', 'created_at', 'updated_at']

    def validate_applicant_gender(self, value):
        """Ensure applicant is female."""
        if value != Gender.FEMALE:
            raise serializers.ValidationError('Applicant must be female for PMUY V3.')
        return value

    def validate_is_migrant(self, value):
        """Ensure is_migrant is True."""
        if not value:
            raise serializers.ValidationError('Application must be for migrant households.')
        return value

    def validate_applicant_dob(self, value):
        """Validate applicant age."""
        from datetime import date
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))

        if age < 18:
            raise serializers.ValidationError(f'Applicant must be at least 18 years old. Current age: {age}')

        if age > 120:
            raise serializers.ValidationError(f'Invalid date of birth. Age: {age}')

        return value

    def validate_addresses(self, value):
        """Validate addresses."""
        if not value:
            return value

        address_types = [addr['address_type'] for addr in value]

        # Check for duplicates
        if len(address_types) != len(set(address_types)):
            raise serializers.ValidationError('Duplicate address types found.')

        return value

    def validate_family_members(self, value):
        """Validate family members."""
        if not value:
            return value

        # Check for multiple SELF members
        self_count = sum(1 for fm in value if fm['relation_to_applicant'] == RelationToApplicant.SELF)
        if self_count > 1:
            raise serializers.ValidationError('Only one SELF member allowed.')

        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create application with nested data."""
        addresses_data = validated_data.pop('addresses', [])
        family_members_data = validated_data.pop('family_members', [])

        # Create application
        application = UjjwalaV3Application.objects.create(**validated_data)

        # Create addresses
        for address_data in addresses_data:
            UjjwalaV3Address.objects.create(application=application, **address_data)

        # Create family members
        for fm_data in family_members_data:
            UjjwalaV3FamilyMember.objects.create(application=application, **fm_data)

        return application

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update application with nested data."""
        addresses_data = validated_data.pop('addresses', None)
        family_members_data = validated_data.pop('family_members', None)

        # Update application
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update addresses if provided
        if addresses_data is not None:
            # Delete existing and create new (simpler approach)
            instance.addresses.all().delete()
            for address_data in addresses_data:
                UjjwalaV3Address.objects.create(application=instance, **address_data)

        # Update family members if provided
        if family_members_data is not None:
            # Delete existing and create new
            instance.family_members.all().delete()
            for fm_data in family_members_data:
                UjjwalaV3FamilyMember.objects.create(application=instance, **fm_data)

        return instance


class ApplicationSubmitSerializer(serializers.Serializer):
    """Serializer for application submission action."""

    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Validate that application can be submitted."""
        application = self.context['application']

        # Check all consents
        if not all([
            application.aadhaar_consent_signed,
            application.agrees_to_dbtl,
            application.agrees_pre_installation_check,
            application.agrees_mandatory_inspections,
            application.declares_no_existing_lpg_or_png_connection,
            application.declares_use_for_domestic_cooking_only,
            application.consent_data_sharing_omc_bank,
        ]):
            raise serializers.ValidationError('All mandatory consents must be signed.')

        # Check required addresses
        if not application.addresses.filter(address_type=AddressType.CURRENT).exists():
            raise serializers.ValidationError('Current address is required.')

        if not application.addresses.filter(address_type=AddressType.PERMANENT).exists():
            raise serializers.ValidationError('Permanent address is required.')

        # Check family members
        if not application.family_members.filter(relation_to_applicant=RelationToApplicant.SELF).exists():
            raise serializers.ValidationError('Applicant must be added as SELF family member.')

        # Check required documents (as per FSM requirements)
        required_docs = [
            DocumentType.CURRENT_ADDRESS_POA,
            DocumentType.PERMANENT_ADDRESS_POA,
            DocumentType.FAMILY_COMPOSITION_DOC,
            DocumentType.DEPRIVATION_DECLARATION,
            DocumentType.BANK_PROOF,
            DocumentType.MIGRANT_DECLARATION,
        ]
        missing_docs = []
        for doc_type in required_docs:
            if not application.documents.filter(doc_type=doc_type).exists():
                missing_docs.append(doc_type)

        if missing_docs:
            raise serializers.ValidationError(
                f"Missing required documents: {', '.join(missing_docs)}"
            )

        # Validate each family member has Aadhaar documents
        for member in application.family_members.all():
            has_front = application.documents.filter(
                family_member=member,
                doc_type=DocumentType.AADHAAR_FRONT
            ).exists()
            has_back = application.documents.filter(
                family_member=member,
                doc_type=DocumentType.AADHAAR_BACK
            ).exists()

            if not (has_front and has_back):
                raise serializers.ValidationError(
                    f"Family member {member.full_name} missing Aadhaar documents (front and back required)"
                )

        # Check for duplicate Aadhaar numbers within application
        aadhaar_numbers = list(
            application.family_members.values_list('aadhaar_number', flat=True)
        )
        if len(aadhaar_numbers) != len(set(aadhaar_numbers)):
            raise serializers.ValidationError("Duplicate Aadhaar numbers found in family members")

        # Validate migrant status (different states)
        current_addr = application.get_current_address()
        permanent_addr = application.get_permanent_address()

        if current_addr and permanent_addr:
            if current_addr.state == permanent_addr.state:
                raise serializers.ValidationError(
                    "For migrant applications, CURRENT and PERMANENT addresses must be in different states"
                )

        return data


class ApplicationApprovalSerializer(serializers.Serializer):
    """Serializer for application approval/rejection actions."""

    action = serializers.ChoiceField(choices=['APPROVE', 'REJECT'])
    remarks = serializers.CharField(required=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Validate approval/rejection."""
        if data['action'] == 'REJECT' and not data.get('rejection_reason'):
            raise serializers.ValidationError({
                'rejection_reason': 'Rejection reason is required when rejecting.'
            })
        return data
