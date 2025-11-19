"""
Enumerations and Choice Classes for Ujjwala V3 Application

This module contains all TextChoices classes used throughout the Ujjwala V3
application for maintaining data consistency and type safety.
"""

from django.db import models


class Gender(models.TextChoices):
    """Gender choices for applicant and family members."""
    MALE = 'M', 'Male'
    FEMALE = 'F', 'Female'
    OTHER = 'O', 'Other'


class Caste(models.TextChoices):
    """Caste/Category choices as per government classification."""
    SC = 'SC', 'Scheduled Caste'
    ST = 'ST', 'Scheduled Tribe'
    OBC = 'OBC', 'Other Backward Class'
    GENERAL = 'GENERAL', 'General'
    OTHERS = 'OTHERS', 'Others'


class FamilyDocumentType(models.TextChoices):
    """Types of family composition documents."""
    RATION_CARD = 'RATION_CARD', 'Ration Card'
    SELF_DECLARATION_MIGRANT = 'SELF_DECLARATION_MIGRANT', 'Self Declaration (Migrant)'
    OTHER = 'OTHER', 'Other Document'


class LPGConnectionType(models.TextChoices):
    """LPG connection cylinder types."""
    SINGLE_14_2KG = 'SINGLE_14_2KG', 'Single 14.2 KG Cylinder'
    SINGLE_5KG = 'SINGLE_5KG', 'Single 5 KG Cylinder'
    DOUBLE_5KG = 'DOUBLE_5KG', 'Double 5 KG Cylinders'


class ApplicationStatus(models.TextChoices):
    """Application lifecycle status."""
    DRAFT = 'DRAFT', 'Draft'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    UNDER_VERIFICATION = 'UNDER_VERIFICATION', 'Under Verification'
    VERIFICATION_FAILED = 'VERIFICATION_FAILED', 'Verification Failed'
    REJECTED = 'REJECTED', 'Rejected'
    APPROVED = 'APPROVED', 'Approved'
    CONNECTION_ISSUED = 'CONNECTION_ISSUED', 'Connection Issued'
    CANCELLED = 'CANCELLED', 'Cancelled'
    ON_HOLD = 'ON_HOLD', 'On Hold'


class AddressType(models.TextChoices):
    """Address type classification."""
    CURRENT = 'CURRENT', 'Current Address (Connection Location)'
    PERMANENT = 'PERMANENT', 'Permanent Address (As per Aadhaar)'
    OTHER = 'OTHER', 'Other Address'


class RelationToApplicant(models.TextChoices):
    """Family member relationship to applicant."""
    SELF = 'SELF', 'Self (Applicant)'
    FATHER = 'FATHER', 'Father'
    MOTHER = 'MOTHER', 'Mother'
    HUSBAND = 'HUSBAND', 'Husband'
    WIFE = 'WIFE', 'Wife'
    SON = 'SON', 'Son'
    DAUGHTER = 'DAUGHTER', 'Daughter'
    BROTHER = 'BROTHER', 'Brother'
    SISTER = 'SISTER', 'Sister'
    GRANDFATHER = 'GRANDFATHER', 'Grandfather'
    GRANDMOTHER = 'GRANDMOTHER', 'Grandmother'
    GRANDSON = 'GRANDSON', 'Grandson'
    GRANDDAUGHTER = 'GRANDDAUGHTER', 'Granddaughter'
    UNCLE = 'UNCLE', 'Uncle'
    AUNT = 'AUNT', 'Aunt'
    NEPHEW = 'NEPHEW', 'Nephew'
    NIECE = 'NIECE', 'Niece'
    FATHER_IN_LAW = 'FATHER_IN_LAW', 'Father-in-law'
    MOTHER_IN_LAW = 'MOTHER_IN_LAW', 'Mother-in-law'
    SON_IN_LAW = 'SON_IN_LAW', 'Son-in-law'
    DAUGHTER_IN_LAW = 'DAUGHTER_IN_LAW', 'Daughter-in-law'
    OTHER = 'OTHER', 'Other Relation'


class DocumentType(models.TextChoices):
    """Document types for file uploads."""
    # Aadhaar Documents
    AADHAAR_FRONT = 'AADHAAR_FRONT', 'Aadhaar Front'
    AADHAAR_BACK = 'AADHAAR_BACK', 'Aadhaar Back'
    AADHAAR_XML = 'AADHAAR_XML', 'Aadhaar XML (DigiLocker)'

    # Address Proof Documents
    CURRENT_ADDRESS_POA = 'CURRENT_ADDRESS_POA', 'Current Address Proof of Address'
    PERMANENT_ADDRESS_POA = 'PERMANENT_ADDRESS_POA', 'Permanent Address Proof of Address'

    # Family & Migration Documents
    FAMILY_COMPOSITION_DOC = 'FAMILY_COMPOSITION_DOC', 'Family Composition / Ration Card'
    MIGRANT_DECLARATION = 'MIGRANT_DECLARATION', 'Migrant Declaration (Annexure-I)'
    DEPRIVATION_DECLARATION = 'DEPRIVATION_DECLARATION', 'Deprivation Declaration'

    # Bank Documents
    BANK_PROOF = 'BANK_PROOF', 'Bank Proof (Passbook/Statement/Cheque)'
    BANK_PASSBOOK = 'BANK_PASSBOOK', 'Bank Passbook Copy'
    CANCELLED_CHEQUE = 'CANCELLED_CHEQUE', 'Cancelled Cheque'

    # Photos
    APPLICANT_PHOTO = 'APPLICANT_PHOTO', 'Applicant Photograph'
    FAMILY_PHOTO = 'FAMILY_PHOTO', 'Family Photograph'

    # Kitchen & Installation
    KITCHEN_PHOTO = 'KITCHEN_PHOTO', 'Kitchen Photograph'
    LPG_INSTALLATION_AREA_PHOTO = 'LPG_INSTALLATION_AREA_PHOTO', 'LPG Installation Area Photo'

    # Signature
    APPLICANT_SIGNATURE = 'APPLICANT_SIGNATURE', 'Applicant Signature'

    # Other Supporting Documents
    IDENTITY_PROOF = 'IDENTITY_PROOF', 'Identity Proof'
    CASTE_CERTIFICATE = 'CASTE_CERTIFICATE', 'Caste Certificate'
    INCOME_CERTIFICATE = 'INCOME_CERTIFICATE', 'Income Certificate'
    OTHER = 'OTHER', 'Other Supporting Document'


class POACode(models.TextChoices):
    """Proof of Address document codes as per PMUY guidelines."""
    POA01 = 'POA01', 'POA01 - Aadhaar Card'
    POA02 = 'POA02', 'POA02 - Passport'
    POA03 = 'POA03', 'POA03 - Voter ID Card'
    POA04 = 'POA04', 'POA04 - Driving License'
    POA05 = 'POA05', 'POA05 - Electricity Bill (< 2 months)'
    POA06 = 'POA06', 'POA06 - Telephone Bill (< 2 months)'
    POA07 = 'POA07', 'POA07 - Water Bill (< 2 months)'
    POA08 = 'POA08', 'POA08 - Bank Statement (< 3 months)'
    POA09 = 'POA09', 'POA09 - Ration Card'
    POA10 = 'POA10', 'POA10 - Property Tax Receipt'
    POA11 = 'POA11', 'POA11 - Rent Agreement (registered)'
    POA12 = 'POA12', 'POA12 - Employer Certificate (with address)'
    POA13 = 'POA13', 'POA13 - Gas Connection Bill'
    POA14 = 'POA14', 'POA14 - Broadband Bill (< 2 months)'
    POA15 = 'POA15', 'POA15 - Post Office Passbook'
    POA16 = 'POA16', 'POA16 - Insurance Policy'
    POA17 = 'POA17', 'POA17 - Domicile Certificate'
    POA18 = 'POA18', 'POA18 - Marriage Certificate'
    POA19 = 'POA19', 'POA19 - Birth Certificate'
    POA20 = 'POA20', 'POA20 - School/College ID Card'
    POA21 = 'POA21', 'POA21 - Municipal/Panchayat Certificate'
    POA22 = 'POA22', 'POA22 - Revenue Record (Patawari/Tehsildar)'
    POA23 = 'POA23', 'POA23 - Arms License'
    POA24 = 'POA24', 'POA24 - Court Order/Decree'
    POA25 = 'POA25', 'POA25 - Migrant Certificate / Other Government-issued Document'


class VerificationStatus(models.TextChoices):
    """Status for various verification checks."""
    PENDING = 'PENDING', 'Pending'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    VERIFIED = 'VERIFIED', 'Verified'
    FAILED = 'FAILED', 'Failed'
    SKIPPED = 'SKIPPED', 'Skipped'


class MaritalStatusEnum(models.TextChoices):
    """Marital status choices."""
    MARRIED = 'MARRIED', 'Married'
    UNMARRIED = 'UNMARRIED', 'Unmarried'
    DIVORCED = 'DIVORCED', 'Divorced'
    WIDOWED = 'WIDOWED', 'Widowed'
    SEPARATED = 'SEPARATED', 'Separated'
