"""
Migration service for migrating Ujjwala V2 applications to Ujjwala V3.

This module provides utilities to migrate applications from the legacy
Ujjwala V2 schema to the new Ujjwala V3 schema.
"""

import logging
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from ujjwala.models import UjjwalaV2Application
from ujjwala_v3.models import (
    UjjwalaV3Application,
    UjjwalaV3Address,
    UjjwalaV3FamilyMember,
    UjjwalaV3Document
)
from ujjwala_v3.enums import (
    AddressType,
    ApplicationStatus,
    Gender,
    Caste,
    MaritalStatusEnum,
    RelationToApplicant,
    VerificationStatus,
    LPGConnectionType
)

logger = logging.getLogger(__name__)


class UjjwalaV2ToV3MigrationService:
    """Service class to handle migration from V2 to V3."""

    def __init__(self):
        self.migration_stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

    def migrate_application(
        self,
        v2_app: UjjwalaV2Application,
        skip_if_exists: bool = True
    ) -> Tuple[Optional[UjjwalaV3Application], bool, str]:
        """
        Migrate a single V2 application to V3.

        Args:
            v2_app: UjjwalaV2Application instance to migrate
            skip_if_exists: Skip if consumer_id already exists in V3

        Returns:
            Tuple of (UjjwalaV3Application instance or None, success bool, message)
        """
        try:
            # Check if already migrated
            if skip_if_exists and v2_app.consumer_id:
                if UjjwalaV3Application.objects.filter(
                    application_number=v2_app.consumer_id
                ).exists():
                    return None, False, f"Application {v2_app.consumer_id} already exists in V3"

            with transaction.atomic():
                # Create V3 application
                v3_app = self._create_v3_application(v2_app)

                # Create address if available
                if v2_app.address_json:
                    self._create_v3_address(v2_app, v3_app)

                # Migrate family members
                self._migrate_family_members(v2_app, v3_app)

                # Migrate documents
                self._migrate_documents(v2_app, v3_app)

                return v3_app, True, "Migration successful"

        except Exception as e:
            logger.exception(f"Error migrating application {v2_app.pk}: {str(e)}")
            return None, False, f"Error: {str(e)}"

    def _create_v3_application(self, v2_app: UjjwalaV2Application) -> UjjwalaV3Application:
        """Create V3 application from V2 data."""

        # Map status
        status_mapping = {
            'DOCUMENTS_UPLOADED': ApplicationStatus.DRAFT,
            'EKYC_SUBMITTED': ApplicationStatus.SUBMITTED,
            'NIC_CLEARED': ApplicationStatus.UNDER_VERIFICATION,
            'LEGAL_DOCUMENTS_ACCEPTED': ApplicationStatus.APPROVED,
            'CONNECTION_APPROVED': ApplicationStatus.APPROVED,
            'CONNECTION_DISBURSED': ApplicationStatus.CONNECTION_ISSUED,
            'REJECTED': ApplicationStatus.REJECTED,
        }

        v3_status = status_mapping.get(
            str(v2_app.status),
            ApplicationStatus.DRAFT
        )

        # Map marital status
        marital_status_mapping = {
            'MARRIED': MaritalStatusEnum.MARRIED,
            'UNMARRIED': MaritalStatusEnum.UNMARRIED,
            'DIVORCED': MaritalStatusEnum.DIVORCED,
            'WIDOWED': MaritalStatusEnum.WIDOWED,
            'SEPARATED': MaritalStatusEnum.SEPARATED,
        }

        v3_marital_status = marital_status_mapping.get(
            str(v2_app.marital_status),
            MaritalStatusEnum.MARRIED
        )

        # Parse name (assume full name for now)
        name_parts = v2_app.name.split(' ', 2) if v2_app.name else ['', '', '']
        first_name = name_parts[0] if len(name_parts) > 0 else ''
        middle_name = name_parts[1] if len(name_parts) > 1 else ''
        last_name = name_parts[2] if len(name_parts) > 2 else ''

        # Create V3 application
        v3_app = UjjwalaV3Application.objects.create(
            # Basic info
            applicant_full_name=v2_app.name or 'Unknown',
            applicant_first_name=first_name or 'Unknown',
            applicant_middle_name=middle_name or None,
            applicant_last_name=last_name or None,
            applicant_gender=Gender.FEMALE,  # PMUY V3 requires female
            applicant_dob=timezone.now().date() - timezone.timedelta(days=365*25),  # Default age 25
            applicant_aadhaar_number=v2_app.application_id_kyc_no or f"TEMP{v2_app.pk:012d}",
            applicant_mobile=v2_app.contact_mobile or '0000000000',
            applicant_email=None,
            caste=Caste.GENERAL,
            is_migrant=True,

            # Marital info
            marital_status=v3_marital_status,
            marriage_date=v2_app.marriage_date,

            # eKYC fields (from V2)
            ekyc_date=v2_app.ekyc_date,
            ekyc_channel=v2_app.ekyc_channel,
            ekyc_last_attempt_log=v2_app.ekyc_last_attempt_log,
            ekyc_cleared=v2_app.ekyc_cleared,

            # Location tracking (from V2)
            latitude=v2_app.latitude,
            longitude=v2_app.longitude,
            accuracy=v2_app.accuracy,

            # Version
            version=v2_app.version or 'V2',

            # Bank details
            bank_account_name=v2_app.name or 'Unknown',
            bank_name='Unknown',  # Not in V2
            bank_branch='Unknown',  # Not in V2
            bank_ifsc=v2_app.ifsc_code or 'XXXX0000000',
            bank_account_number=v2_app.bank_account_number or '000000000000',

            # LPG connection type
            lpg_connection_type=self._map_product_to_connection_type(v2_app.product),

            # Application tracking
            application_number=v2_app.consumer_id,
            status=v3_status,

            # Timestamps
            submitted_at=v2_app.created_on if v3_status != ApplicationStatus.DRAFT else None,

            # Verification status
            bank_verification_status=VerificationStatus.PENDING,

            # Users
            submitted_by=v2_app.filled_by,
            verified_by=v2_app.filled_by,
        )

        # Copy tags from V2 to V3
        if hasattr(v2_app, 'tags') and v2_app.tags.exists():
            for tag in v2_app.tags.all():
                v3_app.tags.add(tag)

        return v3_app

    def _create_v3_address(
        self,
        v2_app: UjjwalaV2Application,
        v3_app: UjjwalaV3Application
    ) -> Optional[UjjwalaV3Address]:
        """Create V3 address from V2 address_json."""
        try:
            address_data = v2_app.address_json
            if not address_data:
                return None

            # Create CURRENT address (V2 doesn't distinguish, so use same for both)
            v3_address = UjjwalaV3Address.objects.create(
                application=v3_app,
                address_type=AddressType.CURRENT,
                house_flat_no=address_data.get('house_no', 'N/A'),
                floor_number=address_data.get('floor', None),
                building_colony=address_data.get('colony', None),
                street_road=address_data.get('street', None),
                village_panchayat_area=address_data.get('area', None),
                block_sub_district=address_data.get('block', None),
                district=address_data.get('district', 'Unknown'),
                city_town=address_data.get('city', 'Unknown'),
                state=address_data.get('state', 'Unknown'),
                pincode=address_data.get('pincode', '000000'),
                landmark=address_data.get('landmark', None),
                area_post_office_name=address_data.get('post_office', None),
                poa_code='POA01',  # Default to Aadhaar
                latitude=float(v2_app.latitude) if v2_app.latitude else None,
                longitude=float(v2_app.longitude) if v2_app.longitude else None,
            )

            # Create PERMANENT address (same as current for V2 migration)
            UjjwalaV3Address.objects.create(
                application=v3_app,
                address_type=AddressType.PERMANENT,
                house_flat_no=address_data.get('house_no', 'N/A'),
                floor_number=address_data.get('floor', None),
                building_colony=address_data.get('colony', None),
                street_road=address_data.get('street', None),
                village_panchayat_area=address_data.get('area', None),
                block_sub_district=address_data.get('block', None),
                district=address_data.get('district', 'Unknown'),
                city_town=address_data.get('city', 'Unknown'),
                state=address_data.get('state', 'Unknown'),
                pincode=address_data.get('pincode', '000000'),
                landmark=address_data.get('landmark', None),
                area_post_office_name=address_data.get('post_office', None),
                poa_code='POA01',
            )

            return v3_address

        except Exception as e:
            logger.warning(f"Could not create address for {v2_app.pk}: {str(e)}")
            return None

    def _migrate_family_members(
        self,
        v2_app: UjjwalaV2Application,
        v3_app: UjjwalaV3Application
    ) -> List[UjjwalaV3FamilyMember]:
        """Migrate family members from V2 to V3."""
        v3_members = []

        try:
            # Get V2 family members
            v2_members = v2_app.family_members.all()

            for v2_member in v2_members:
                # Map relation
                relation_mapping = {
                    'SELF': RelationToApplicant.SELF,
                    'FATHER': RelationToApplicant.FATHER,
                    'MOTHER': RelationToApplicant.MOTHER,
                    'HUSBAND': RelationToApplicant.HUSBAND,
                    'WIFE': RelationToApplicant.WIFE,
                    'SON': RelationToApplicant.SON,
                    'DAUGHTER': RelationToApplicant.DAUGHTER,
                    'BROTHER': RelationToApplicant.BROTHER,
                    'SISTER': RelationToApplicant.SISTER,
                }

                v3_relation = relation_mapping.get(
                    str(v2_member.relation),
                    RelationToApplicant.OTHER
                )

                # Map gender
                gender_mapping = {
                    'MALE': Gender.MALE,
                    'M': Gender.MALE,
                    'FEMALE': Gender.FEMALE,
                    'F': Gender.FEMALE,
                }

                v3_gender = gender_mapping.get(
                    str(v2_member.gender).upper(),
                    Gender.OTHER
                )

                v3_member = UjjwalaV3FamilyMember.objects.create(
                    application=v3_app,
                    full_name=v2_member.name or 'Unknown',
                    relation_to_applicant=v3_relation,
                    gender=v3_gender,
                    aadhaar_number=v2_member.uid_no or f"TEMP{v2_member.pk:012d}",
                    dob=v2_member.dob or timezone.now().date() - timezone.timedelta(days=365*25),
                    uid_front_link=getattr(v2_member, 'uid_front_link', None),
                    uid_back_link=getattr(v2_member, 'uid_back_link', None),
                    uid_original_front_link=getattr(v2_member, 'uid_original_front_link', None),
                    uid_original_back_link=getattr(v2_member, 'uid_original_back_link', None),
                    uid_check_result=getattr(v2_member, 'uid_check_result', None),
                    is_valid_uid=getattr(v2_member, 'is_valid_uid', False),
                    validated=getattr(v2_member, 'validated', False),
                    uid_front_file_size=getattr(v2_member, 'uid_front_file_size', None),
                    uid_back_file_size=getattr(v2_member, 'uid_back_file_size', None),
                    additional_details=getattr(v2_member, 'additional_details', None),
                    ration_card_available=getattr(v2_member, 'ration_card_available', False),
                )

                v3_members.append(v3_member)

        except Exception as e:
            logger.warning(f"Could not migrate family members for {v2_app.pk}: {str(e)}")

        return v3_members

    def _migrate_documents(
        self,
        v2_app: UjjwalaV2Application,
        v3_app: UjjwalaV3Application
    ) -> List[UjjwalaV3Document]:
        """Migrate documents from V2 to V3."""
        v3_documents = []

        # Note: V2 document structure needs to be mapped
        # This is a placeholder - adjust based on actual V2 document model

        return v3_documents

    def _map_product_to_connection_type(self, product: Optional[str]) -> str:
        """Map V2 product to V3 LPG connection type."""
        if not product:
            return LPGConnectionType.SINGLE_14_2KG

        product_lower = product.lower()

        if '5kg' in product_lower:
            if 'double' in product_lower or '2' in product_lower:
                return LPGConnectionType.DOUBLE_5KG
            return LPGConnectionType.SINGLE_5KG

        return LPGConnectionType.SINGLE_14_2KG

    def migrate_batch(
        self,
        v2_app_ids: Optional[List[int]] = None,
        limit: Optional[int] = None,
        skip_if_exists: bool = True
    ) -> Dict:
        """
        Migrate multiple applications in batch.

        Args:
            v2_app_ids: List of V2 application IDs to migrate (None = all)
            limit: Maximum number of applications to migrate
            skip_if_exists: Skip if already migrated

        Returns:
            Dictionary with migration statistics
        """
        self.migration_stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

        # Get V2 applications to migrate
        if v2_app_ids:
            v2_apps = UjjwalaV2Application.objects.filter(pk__in=v2_app_ids)
        else:
            v2_apps = UjjwalaV2Application.objects.all()

        if limit:
            v2_apps = v2_apps[:limit]

        self.migration_stats['total'] = v2_apps.count()

        for v2_app in v2_apps:
            v3_app, success, message = self.migrate_application(v2_app, skip_if_exists)

            if success:
                self.migration_stats['success'] += 1
                logger.info(f"Migrated application {v2_app.pk} -> {v3_app.pk}")
            elif "already exists" in message:
                self.migration_stats['skipped'] += 1
                logger.info(f"Skipped application {v2_app.pk}: {message}")
            else:
                self.migration_stats['failed'] += 1
                self.migration_stats['errors'].append({
                    'v2_app_id': v2_app.pk,
                    'error': message
                })
                logger.error(f"Failed to migrate application {v2_app.pk}: {message}")

        return self.migration_stats
