"""
Django Models for Ujjwala V3 Application - PMUY for Migrant Households

This module defines the core data models for Pradhan Mantri Ujjwala Yojana (PMUY) V3,
specifically designed for migrant households requiring LPG connections.

Core Models:
    - UjjwalaV3Application: Main application model
    - UjjwalaV3Address: Address storage (Current/Permanent)
    - UjjwalaV3FamilyMember: Family member details
    - UjjwalaV3Document: Document/file storage
    - UjjwalaV3AuditLog: Audit trail for application changes
"""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.db import models
from django.db.models import Q, CheckConstraint, UniqueConstraint
from django.utils import timezone
from django_fsm import FSMField, transition

from .enums import (
    Gender, Caste, FamilyDocumentType, LPGConnectionType,
    ApplicationStatus, AddressType, RelationToApplicant,
    DocumentType, POACode, IndianState, VerificationStatus
)
from .validators import (
    validate_aadhaar_number, validate_mobile_number, validate_ifsc_code,
    validate_pincode, validate_bank_account_number, validate_adult_dob,
    validate_future_date, validate_name
)


class TimeStampedModel(models.Model):
    """Abstract base class providing timestamp fields."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class UjjwalaV3Application(TimeStampedModel):
    """
    Main application model for Ujjwala V3 (Migrant Households).

    Represents a single PMUY application submitted by a migrant household.
    All applicants must be adult women (>= 18 years) and is_migrant must be True.

    Related Models:
        - addresses: Related UjjwalaV3Address instances (CURRENT, PERMANENT)
        - family_members: Related UjjwalaV3FamilyMember instances
        - documents: Related UjjwalaV3Document instances
        - audit_logs: Related UjjwalaV3AuditLog instances
    """

    # ==================== APPLICANT DETAILS ====================
    applicant_full_name = models.CharField(
        max_length=200,
        validators=[validate_name],
        db_index=True,
        help_text='Full name of applicant as per Aadhaar'
    )
    applicant_first_name = models.CharField(
        max_length=100,
        validators=[validate_name],
        help_text='First name of applicant'
    )
    applicant_middle_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        validators=[validate_name],
        help_text='Middle name of applicant (optional)'
    )
    applicant_last_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        validators=[validate_name],
        help_text='Last name of applicant (optional)'
    )

    applicant_gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        default=Gender.FEMALE,
        help_text='Gender - Must be Female for PMUY V3'
    )

    applicant_dob = models.DateField(
        validators=[validate_adult_dob, validate_future_date],
        db_index=True,
        help_text='Date of birth as per Aadhaar (Must be >= 18 years)'
    )

    applicant_aadhaar_number = models.CharField(
        max_length=12,
        unique=True,
        validators=[validate_aadhaar_number, MinLengthValidator(12), MaxLengthValidator(12)],
        db_index=True,
        help_text='12-digit Aadhaar number (unique)'
    )

    applicant_mobile = models.CharField(
        max_length=10,
        validators=[validate_mobile_number, MinLengthValidator(10), MaxLengthValidator(10)],
        db_index=True,
        help_text='10-digit mobile number'
    )

    applicant_email = models.EmailField(
        max_length=254,
        null=True,
        blank=True,
        db_index=True,
        help_text='Email address (optional)'
    )

    caste = models.CharField(
        max_length=20,
        choices=Caste.choices,
        default=Caste.GENERAL,
        db_index=True,
        help_text='Caste/Category as per government classification'
    )

    is_migrant = models.BooleanField(
        default=True,
        help_text='Migrant status - Must be True for PMUY V3'
    )

    # ==================== FAMILY COMPOSITION DOCUMENT METADATA ====================
    family_doc_issuing_state = models.CharField(
        max_length=2,
        choices=IndianState.choices,
        null=True,
        blank=True,
        db_index=True,
        help_text='State that issued the family composition document'
    )

    family_doc_type = models.CharField(
        max_length=50,
        choices=FamilyDocumentType.choices,
        null=True,
        blank=True,
        help_text='Type of family composition document'
    )

    family_doc_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Document number of family composition document'
    )

    is_deprivation_decl_signed = models.BooleanField(
        default=False,
        help_text='Whether deprivation declaration has been signed'
    )

    # ==================== BANK DETAILS ====================
    bank_account_name = models.CharField(
        max_length=200,
        validators=[validate_name],
        help_text='Account holder name as per bank records'
    )

    bank_name = models.CharField(
        max_length=200,
        help_text='Name of the bank'
    )

    bank_branch = models.CharField(
        max_length=200,
        help_text='Bank branch name'
    )

    bank_ifsc = models.CharField(
        max_length=11,
        validators=[validate_ifsc_code, MinLengthValidator(11), MaxLengthValidator(11)],
        db_index=True,
        help_text='11-character IFSC code'
    )

    bank_account_number = models.CharField(
        max_length=18,
        validators=[validate_bank_account_number],
        help_text='Bank account number (9-18 characters)'
    )

    # ==================== LPG CONNECTION INFO ====================
    lpg_connection_type = models.CharField(
        max_length=20,
        choices=LPGConnectionType.choices,
        default=LPGConnectionType.SINGLE_14_2KG,
        db_index=True,
        help_text='Type of LPG connection/cylinder'
    )

    is_new_connection = models.BooleanField(
        default=True,
        help_text='Whether this is a new connection request'
    )

    connection_remarks = models.TextField(
        null=True,
        blank=True,
        help_text='Additional remarks about the connection'
    )

    # ==================== CONSENTS & DECLARATIONS ====================
    aadhaar_consent_signed = models.BooleanField(
        default=False,
        help_text='Consent for Aadhaar-based authentication'
    )

    agrees_to_dbtl = models.BooleanField(
        default=False,
        help_text='Agreement to receive subsidy via DBTL (Direct Benefit Transfer for LPG)'
    )

    agrees_pre_installation_check = models.BooleanField(
        default=False,
        help_text='Agreement for pre-installation safety check'
    )

    agrees_mandatory_inspections = models.BooleanField(
        default=False,
        help_text='Agreement for mandatory safety inspections'
    )

    declares_no_existing_lpg_or_png_connection = models.BooleanField(
        default=False,
        help_text='Declaration of no existing LPG or PNG connection in household'
    )

    declares_use_for_domestic_cooking_only = models.BooleanField(
        default=False,
        help_text='Declaration to use LPG for domestic cooking only'
    )

    consent_data_sharing_omc_bank = models.BooleanField(
        default=False,
        help_text='Consent for data sharing with OMC and bank'
    )

    # ==================== APPLICATION LIFECYCLE ====================
    application_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text='Unique application reference number (auto-generated)'
    )

    status = FSMField(
        max_length=30,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.DRAFT,
        db_index=True,
        protected=True,
        help_text='Current status of the application (FSM-controlled)'
    )

    rejection_reason = models.TextField(
        null=True,
        blank=True,
        help_text='Reason for rejection if status is REJECTED'
    )

    # ==================== WORKFLOW TIMESTAMPS ====================
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Timestamp when application was submitted'
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when application verification completed'
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when application was approved'
    )

    connection_issued_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when LPG connection was issued'
    )

    verification_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when verification process started'
    )

    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when application was rejected'
    )

    # ==================== VERIFICATION TRACKING ====================
    aadhaar_verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        help_text='Status of Aadhaar verification'
    )

    bank_verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        help_text='Status of bank account verification'
    )

    address_verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        help_text='Status of address verification'
    )

    # ==================== ADDITIONAL METADATA ====================
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_ujjwala_v3_applications',
        help_text='User who submitted the application'
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_ujjwala_v3_applications',
        help_text='User who verified the application'
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_ujjwala_v3_applications',
        help_text='User who approved the application'
    )

    class Meta:
        db_table = 'ujjwala_v3_application'
        verbose_name = 'Ujjwala V3 Application'
        verbose_name_plural = 'Ujjwala V3 Applications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['applicant_mobile', 'status']),
            models.Index(fields=['applicant_aadhaar_number']),
            models.Index(fields=['application_number']),
            models.Index(fields=['submitted_at']),
        ]
        constraints = [
            CheckConstraint(
                check=Q(applicant_gender=Gender.FEMALE),
                name='ujjwala_v3_applicant_must_be_female'
            ),
            CheckConstraint(
                check=Q(is_migrant=True),
                name='ujjwala_v3_must_be_migrant'
            ),
        ]

    def __str__(self):
        return f'{self.application_number or self.id} - {self.applicant_full_name}'

    def clean(self):
        """Custom validation for the model."""
        super().clean()

        # Ensure applicant is female
        if self.applicant_gender != Gender.FEMALE:
            raise ValidationError({
                'applicant_gender': 'Applicant must be female for PMUY V3.'
            })

        # Ensure is_migrant is True
        if not self.is_migrant:
            raise ValidationError({
                'is_migrant': 'Application must be for migrant households (is_migrant must be True).'
            })

        # Validate age
        if self.applicant_dob:
            today = date.today()
            age = today.year - self.applicant_dob.year - (
                (today.month, today.day) < (self.applicant_dob.month, self.applicant_dob.day)
            )
            if age < 18:
                raise ValidationError({
                    'applicant_dob': f'Applicant must be at least 18 years old. Current age: {age}'
                })

        # Validate all mandatory consents before submission
        if self.status not in [ApplicationStatus.DRAFT]:
            if not all([
                self.aadhaar_consent_signed,
                self.agrees_to_dbtl,
                self.agrees_pre_installation_check,
                self.agrees_mandatory_inspections,
                self.declares_no_existing_lpg_or_png_connection,
                self.declares_use_for_domestic_cooking_only,
                self.consent_data_sharing_omc_bank,
            ]):
                raise ValidationError(
                    'All mandatory consents and declarations must be signed before submission.'
                )

    def save(self, *args, **kwargs):
        """Override save to generate application number and validate."""
        self.full_clean()

        # Generate application number if not present
        if not self.application_number and self.status != ApplicationStatus.DRAFT:
            self.application_number = self._generate_application_number()

        # Set submitted_at timestamp
        if self.status == ApplicationStatus.SUBMITTED and not self.submitted_at:
            self.submitted_at = timezone.now()

        super().save(*args, **kwargs)

    def _generate_application_number(self):
        """Generate unique application number."""
        # Format: UJJV3-YYYY-XXXXXXXX
        # Example: UJJV3-2024-00001234
        year = timezone.now().year
        # Get count of applications this year
        count = UjjwalaV3Application.objects.filter(
            created_at__year=year
        ).count() + 1
        return f'UJJV3-{year}-{count:08d}'

    @property
    def applicant_age(self):
        """Calculate applicant's current age."""
        if not self.applicant_dob:
            return None
        today = date.today()
        return today.year - self.applicant_dob.year - (
            (today.month, today.day) < (self.applicant_dob.month, self.applicant_dob.day)
        )

    @property
    def is_complete(self):
        """Check if application has all required information."""
        # Check addresses
        has_current_address = self.addresses.filter(address_type=AddressType.CURRENT).exists()
        has_permanent_address = self.addresses.filter(address_type=AddressType.PERMANENT).exists()

        # Check family members (at least applicant as SELF)
        has_self_member = self.family_members.filter(relation_to_applicant=RelationToApplicant.SELF).exists()

        # Check required documents
        required_docs = [
            DocumentType.AADHAAR_FRONT,
            DocumentType.AADHAAR_BACK,
            DocumentType.BANK_PROOF,
            DocumentType.MIGRANT_DECLARATION,
        ]
        has_required_docs = all(
            self.documents.filter(doc_type=doc_type).exists()
            for doc_type in required_docs
        )

        return all([
            has_current_address,
            has_permanent_address,
            has_self_member,
            has_required_docs,
        ])

    def get_current_address(self):
        """Get the current address for this application."""
        return self.addresses.filter(address_type=AddressType.CURRENT).first()

    def get_permanent_address(self):
        """Get the permanent address for this application."""
        return self.addresses.filter(address_type=AddressType.PERMANENT).first()

    def is_migrant_verified(self):
        """Check if migration is verified (different states for current vs permanent)."""
        current_addr = self.get_current_address()
        permanent_addr = self.get_permanent_address()

        if not current_addr or not permanent_addr:
            return False

        # Migrant = different states
        return current_addr.state != permanent_addr.state

    def _validate_required_documents(self):
        """Validate that all required documents are uploaded."""
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
            if not self.documents.filter(doc_type=doc_type).exists():
                missing_docs.append(doc_type)

        if missing_docs:
            raise ValidationError(
                f"Missing required documents: {', '.join(missing_docs)}"
            )

    def _validate_family_members(self):
        """Validate family member requirements."""
        # Check SELF member exists
        self_member = self.family_members.filter(
            relation_to_applicant=RelationToApplicant.SELF
        ).first()

        if not self_member:
            raise ValidationError("Applicant must be added as SELF family member")

        # Validate SELF member matches applicant
        if self_member.aadhaar_number != self.applicant_aadhaar_number:
            raise ValidationError("SELF member Aadhaar must match applicant Aadhaar")

        if self_member.dob != self.applicant_dob:
            raise ValidationError("SELF member DOB must match applicant DOB")

        if self_member.gender != self.applicant_gender:
            raise ValidationError("SELF member gender must match applicant gender")

        # Validate each family member has Aadhaar documents
        for member in self.family_members.all():
            has_front = self.documents.filter(
                family_member=member,
                doc_type=DocumentType.AADHAAR_FRONT
            ).exists()
            has_back = self.documents.filter(
                family_member=member,
                doc_type=DocumentType.AADHAAR_BACK
            ).exists()

            if not (has_front and has_back):
                raise ValidationError(
                    f"Family member {member.full_name} missing Aadhaar documents"
                )

        # Check for duplicate Aadhaar within application
        aadhaar_numbers = list(
            self.family_members.values_list('aadhaar_number', flat=True)
        )
        if len(aadhaar_numbers) != len(set(aadhaar_numbers)):
            raise ValidationError("Duplicate Aadhaar numbers found in family members")

    def _validate_addresses(self):
        """Validate address requirements."""
        if not self.addresses.filter(address_type=AddressType.CURRENT).exists():
            raise ValidationError("CURRENT address is required")

        if not self.addresses.filter(address_type=AddressType.PERMANENT).exists():
            raise ValidationError("PERMANENT address is required")

    def _validate_migrant_status(self):
        """Validate migrant requirements."""
        if not self.is_migrant:
            raise ValidationError("Application must be for migrant households")

        current_addr = self.get_current_address()
        permanent_addr = self.get_permanent_address()

        if current_addr and permanent_addr:
            if current_addr.state == permanent_addr.state:
                raise ValidationError(
                    "For migrant applications, CURRENT and PERMANENT addresses must be in different states"
                )

    def _validate_consents(self):
        """Validate all mandatory consents are signed."""
        if not all([
            self.aadhaar_consent_signed,
            self.agrees_to_dbtl,
            self.agrees_pre_installation_check,
            self.agrees_mandatory_inspections,
            self.declares_no_existing_lpg_or_png_connection,
            self.declares_use_for_domestic_cooking_only,
            self.consent_data_sharing_omc_bank,
        ]):
            raise ValidationError("All mandatory consents and declarations must be signed")

    # ==================== FSM TRANSITIONS ====================

    @transition(
        field=status,
        source=ApplicationStatus.DRAFT,
        target=ApplicationStatus.SUBMITTED
    )
    def submit(self, user=None):
        """
        Submit application for review.

        Validates:
        - All consents signed
        - All required documents uploaded
        - CURRENT and PERMANENT addresses exist
        - SELF family member exists and matches applicant
        - All family members have Aadhaar docs
        - Migrant status verified
        - LPG connection type specified
        """
        # Validate female applicant
        if self.applicant_gender != Gender.FEMALE:
            raise ValidationError("Applicant must be female")

        # Validate age >= 18
        if self.applicant_age < 18:
            raise ValidationError(f"Applicant must be at least 18 years old (current age: {self.applicant_age})")

        # Validate consents
        self._validate_consents()

        # Validate addresses
        self._validate_addresses()

        # Validate family members
        self._validate_family_members()

        # Validate migrant status
        self._validate_migrant_status()

        # Validate required documents
        self._validate_required_documents()

        # Validate LPG connection type
        if not self.lpg_connection_type:
            raise ValidationError("LPG connection type must be specified")

        # Set timestamps and metadata
        self.submitted_at = timezone.now()
        if user:
            self.submitted_by = user

        # Generate application number
        if not self.application_number:
            self.application_number = self._generate_application_number()

    @transition(
        field=status,
        source=ApplicationStatus.SUBMITTED,
        target=ApplicationStatus.UNDER_VERIFICATION
    )
    def start_verification(self, user=None):
        """
        Start verification process.

        Moves application from SUBMITTED to UNDER_VERIFICATION.
        """
        self.verification_started_at = timezone.now()
        if user:
            self.verified_by = user

    @transition(
        field=status,
        source=ApplicationStatus.UNDER_VERIFICATION,
        target=ApplicationStatus.APPROVED
    )
    def approve(self, user=None):
        """
        Approve application.

        Moves application from UNDER_VERIFICATION to APPROVED.
        Only possible after all verifications are complete.
        """
        # Additional validation: ensure all verifications are done
        if self.aadhaar_verification_status != VerificationStatus.VERIFIED:
            raise ValidationError("Aadhaar verification must be completed before approval")

        if self.bank_verification_status != VerificationStatus.VERIFIED:
            raise ValidationError("Bank verification must be completed before approval")

        if self.address_verification_status != VerificationStatus.VERIFIED:
            raise ValidationError("Address verification must be completed before approval")

        self.approved_at = timezone.now()
        self.verified_at = timezone.now()
        if user:
            self.approved_by = user

    @transition(
        field=status,
        source=[
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.UNDER_VERIFICATION,
            ApplicationStatus.VERIFICATION_FAILED
        ],
        target=ApplicationStatus.REJECTED
    )
    def reject(self, reason, user=None):
        """
        Reject application.

        Args:
            reason: Reason for rejection (required)
            user: User performing the rejection
        """
        if not reason:
            raise ValidationError("Rejection reason is required")

        self.rejection_reason = reason
        self.rejected_at = timezone.now()
        if user:
            self.verified_by = user

    @transition(
        field=status,
        source=ApplicationStatus.APPROVED,
        target=ApplicationStatus.CONNECTION_ISSUED
    )
    def issue_connection(self, user=None):
        """
        Issue LPG connection.

        Final step - marks connection as issued.
        Only possible from APPROVED status.
        """
        self.connection_issued_at = timezone.now()


class UjjwalaV3Address(TimeStampedModel):
    """
    Address model for storing all address-related data.

    Each application must have at least two addresses:
    - CURRENT: Where the LPG connection is required
    - PERMANENT: As per Aadhaar / home state

    For migrant applications, CURRENT and PERMANENT addresses should be in different states.
    """

    application = models.ForeignKey(
        'UjjwalaV3Application',
        on_delete=models.CASCADE,
        related_name='addresses',
        help_text='Related application'
    )

    address_type = models.CharField(
        max_length=20,
        choices=AddressType.choices,
        db_index=True,
        help_text='Type of address (CURRENT, PERMANENT, OTHER)'
    )

    # ==================== ADDRESS FIELDS ====================
    house_flat_no = models.CharField(
        max_length=50,
        help_text='House/Flat number'
    )

    floor_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text='Floor number (if applicable)'
    )

    building_colony = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text='Building/Colony/Apartment name'
    )

    street_road = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text='Street/Road name'
    )

    village_panchayat_area = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text='Village/Panchayat/Area/Locality'
    )

    block_sub_district = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text='Block/Sub-district/Tehsil'
    )

    district = models.CharField(
        max_length=200,
        db_index=True,
        help_text='District'
    )

    city_town = models.CharField(
        max_length=200,
        db_index=True,
        help_text='City/Town/Municipality'
    )

    state = models.CharField(
        max_length=2,
        choices=IndianState.choices,
        db_index=True,
        help_text='State/UT code'
    )

    pincode = models.CharField(
        max_length=6,
        validators=[validate_pincode, MinLengthValidator(6), MaxLengthValidator(6)],
        db_index=True,
        help_text='6-digit pincode'
    )

    landmark = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text='Nearby landmark'
    )

    area_post_office_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text='Post office name'
    )

    poa_code = models.CharField(
        max_length=10,
        choices=POACode.choices,
        help_text='Proof of Address document code (POA01-POA25)'
    )

    # ==================== GEOLOCATION (Optional) ====================
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        help_text='Latitude coordinate'
    )

    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        help_text='Longitude coordinate'
    )

    class Meta:
        db_table = 'ujjwala_v3_address'
        verbose_name = 'Ujjwala V3 Address'
        verbose_name_plural = 'Ujjwala V3 Addresses'
        ordering = ['address_type', '-created_at']
        indexes = [
            models.Index(fields=['application', 'address_type']),
            models.Index(fields=['state', 'district']),
            models.Index(fields=['pincode']),
        ]
        constraints = [
            # One application can have only one address of each type
            UniqueConstraint(
                fields=['application', 'address_type'],
                name='unique_address_type_per_application'
            ),
        ]

    def __str__(self):
        return f'{self.get_address_type_display()} - {self.city_town}, {self.state}'

    def get_full_address(self):
        """Return formatted full address string."""
        parts = [
            self.house_flat_no,
            self.floor_number,
            self.building_colony,
            self.street_road,
            self.village_panchayat_area,
            self.block_sub_district,
            self.district,
            self.city_town,
            self.get_state_display(),
            self.pincode,
        ]
        return ', '.join(filter(None, parts))

    def clean(self):
        """Custom validation."""
        super().clean()

        # Validate that application doesn't already have this address type
        if self.application_id:
            existing = UjjwalaV3Address.objects.filter(
                application=self.application,
                address_type=self.address_type
            ).exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError({
                    'address_type': f'Application already has a {self.get_address_type_display()} address.'
                })


class UjjwalaV3FamilyMember(TimeStampedModel):
    """
    Family member model representing household composition.

    The applicant herself must be included as a family member with relation = SELF.
    Each family member's Aadhaar documents are stored in UjjwalaV3Document model.
    """

    application = models.ForeignKey(
        'UjjwalaV3Application',
        on_delete=models.CASCADE,
        related_name='family_members',
        help_text='Related application'
    )

    full_name = models.CharField(
        max_length=200,
        validators=[validate_name],
        help_text='Full name as per Aadhaar'
    )

    relation_to_applicant = models.CharField(
        max_length=20,
        choices=RelationToApplicant.choices,
        db_index=True,
        help_text='Relationship to applicant'
    )

    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        help_text='Gender'
    )

    aadhaar_number = models.CharField(
        max_length=12,
        validators=[validate_aadhaar_number, MinLengthValidator(12), MaxLengthValidator(12)],
        db_index=True,
        help_text='12-digit Aadhaar number'
    )

    dob = models.DateField(
        validators=[validate_future_date],
        help_text='Date of birth as per Aadhaar'
    )

    age_at_application = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Age at the time of application (auto-calculated)'
    )

    class Meta:
        db_table = 'ujjwala_v3_family_member'
        verbose_name = 'Ujjwala V3 Family Member'
        verbose_name_plural = 'Ujjwala V3 Family Members'
        ordering = ['relation_to_applicant', 'dob']
        indexes = [
            models.Index(fields=['application', 'relation_to_applicant']),
            models.Index(fields=['aadhaar_number']),
        ]
        constraints = [
            # Only one SELF member per application
            UniqueConstraint(
                fields=['application', 'relation_to_applicant'],
                condition=Q(relation_to_applicant=RelationToApplicant.SELF),
                name='unique_self_member_per_application'
            ),
        ]

    def __str__(self):
        return f'{self.full_name} ({self.get_relation_to_applicant_display()})'

    def clean(self):
        """Custom validation."""
        super().clean()

        # SELF member must match applicant's details
        if self.relation_to_applicant == RelationToApplicant.SELF:
            if self.application_id:
                app = self.application
                if self.aadhaar_number != app.applicant_aadhaar_number:
                    raise ValidationError({
                        'aadhaar_number': 'SELF member Aadhaar must match applicant Aadhaar.'
                    })
                if self.gender != app.applicant_gender:
                    raise ValidationError({
                        'gender': 'SELF member gender must match applicant gender.'
                    })
                if self.dob != app.applicant_dob:
                    raise ValidationError({
                        'dob': 'SELF member DOB must match applicant DOB.'
                    })

    def save(self, *args, **kwargs):
        """Override save to calculate age."""
        self.full_clean()

        # Calculate age at application
        if self.dob:
            today = date.today()
            self.age_at_application = today.year - self.dob.year - (
                (today.month, today.day) < (self.dob.month, self.dob.day)
            )

        super().save(*args, **kwargs)


class UjjwalaV3Document(TimeStampedModel):
    """
    Central document storage model for all file uploads.

    All documents (Aadhaar photos, POA, bank proofs, declarations, etc.) are stored here.
    Documents can be linked to:
    - Application (required)
    - Family member (optional, for member-specific docs like Aadhaar)
    - Address (optional, for address-specific POA docs)
    """

    application = models.ForeignKey(
        'UjjwalaV3Application',
        on_delete=models.CASCADE,
        related_name='documents',
        help_text='Related application'
    )

    family_member = models.ForeignKey(
        'UjjwalaV3FamilyMember',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='documents',
        help_text='Related family member (for member-specific documents)'
    )

    address = models.ForeignKey(
        'UjjwalaV3Address',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='documents',
        help_text='Related address (for address-specific POA documents)'
    )

    doc_type = models.CharField(
        max_length=50,
        choices=DocumentType.choices,
        db_index=True,
        help_text='Type of document'
    )

    file = models.FileField(
        upload_to='ujjwala_v3_documents/%Y/%m/%d/',
        max_length=500,
        help_text='Uploaded document file'
    )

    file_name = models.CharField(
        max_length=255,
        help_text='Original file name'
    )

    file_size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text='File size in bytes'
    )

    mime_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='MIME type of the file'
    )

    description = models.TextField(
        null=True,
        blank=True,
        help_text='Additional description or notes'
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_ujjwala_v3_documents',
        help_text='User who uploaded the document'
    )

    is_verified = models.BooleanField(
        default=False,
        help_text='Whether document has been verified'
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_ujjwala_v3_documents',
        help_text='User who verified the document'
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when document was verified'
    )

    class Meta:
        db_table = 'ujjwala_v3_document'
        verbose_name = 'Ujjwala V3 Document'
        verbose_name_plural = 'Ujjwala V3 Documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['application', 'doc_type']),
            models.Index(fields=['family_member', 'doc_type']),
            models.Index(fields=['address', 'doc_type']),
            models.Index(fields=['is_verified', 'doc_type']),
        ]

    def __str__(self):
        return f'{self.get_doc_type_display()} - {self.file_name}'

    def clean(self):
        """Custom validation."""
        super().clean()

        # Validate family member documents must have family_member set
        if self.doc_type in [DocumentType.AADHAAR_FRONT, DocumentType.AADHAAR_BACK]:
            if not self.family_member_id:
                raise ValidationError({
                    'family_member': f'{self.get_doc_type_display()} must be linked to a family member.'
                })

        # Validate address POA documents must have address set
        if self.doc_type in [DocumentType.CURRENT_ADDRESS_POA, DocumentType.PERMANENT_ADDRESS_POA]:
            if not self.address_id:
                raise ValidationError({
                    'address': f'{self.get_doc_type_display()} must be linked to an address.'
                })

            # Validate address type matches document type
            if self.address:
                if self.doc_type == DocumentType.CURRENT_ADDRESS_POA:
                    if self.address.address_type != AddressType.CURRENT:
                        raise ValidationError({
                            'address': 'Current address POA must be linked to CURRENT address.'
                        })
                elif self.doc_type == DocumentType.PERMANENT_ADDRESS_POA:
                    if self.address.address_type != AddressType.PERMANENT:
                        raise ValidationError({
                            'address': 'Permanent address POA must be linked to PERMANENT address.'
                        })

    def save(self, *args, **kwargs):
        """Override save to set file metadata."""
        self.full_clean()

        if self.file:
            self.file_size = self.file.size
            if not self.file_name:
                self.file_name = self.file.name

        super().save(*args, **kwargs)


class UjjwalaV3AuditLog(TimeStampedModel):
    """
    Audit log model for tracking all changes to applications.

    Provides a complete audit trail of who did what and when.
    """

    application = models.ForeignKey(
        'UjjwalaV3Application',
        on_delete=models.CASCADE,
        related_name='audit_logs',
        help_text='Related application'
    )

    action = models.CharField(
        max_length=100,
        db_index=True,
        help_text='Action performed (e.g., CREATED, UPDATED, SUBMITTED, APPROVED)'
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ujjwala_v3_audit_actions',
        help_text='User who performed the action'
    )

    changes = models.JSONField(
        null=True,
        blank=True,
        help_text='JSON object containing field changes'
    )

    remarks = models.TextField(
        null=True,
        blank=True,
        help_text='Additional remarks or notes'
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of the actor'
    )

    class Meta:
        db_table = 'ujjwala_v3_audit_log'
        verbose_name = 'Ujjwala V3 Audit Log'
        verbose_name_plural = 'Ujjwala V3 Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['application', 'action', '-created_at']),
            models.Index(fields=['actor', '-created_at']),
        ]

    def __str__(self):
        return f'{self.action} - {self.application.application_number} at {self.created_at}'
