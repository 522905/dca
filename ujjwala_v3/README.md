# Ujjwala V3 - PMUY for Migrant Households

A comprehensive Django + Django REST Framework application for managing **Pradhan Mantri Ujjwala Yojana (PMUY) V3** applications specifically designed for **migrant households**.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Data Models](#data-models)
- [Installation](#installation)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Admin Interface](#admin-interface)
- [Business Rules](#business-rules)
- [Testing](#testing)

---

## 🎯 Overview

This module implements a production-grade data model and REST API for managing LPG (Liquified Petroleum Gas) connection applications under the Pradhan Mantri Ujjwala Yojana (PMUY) scheme for migrant households.

### Key Characteristics

- **Applicant**: Must be an adult woman (≥ 18 years)
- **Migration Status**: All applications are for migrant households (is_migrant = True)
- **Document Management**: Centralized document storage with proper linking
- **Address Management**: Separate models for current and permanent addresses
- **Family Composition**: Track all household members with deduplication
- **Audit Trail**: Complete lifecycle tracking with audit logs

---

## ✨ Features

### Core Functionality

1. **Application Management**
   - Create, read, update, delete (CRUD) applications
   - Multi-step application workflow (Draft → Submitted → Under Verification → Approved → Connection Issued)
   - Comprehensive validation at model and serializer levels
   - Automatic application number generation

2. **Document Management**
   - Centralized document storage (no FileFields on application/address models)
   - Support for multiple document types (Aadhaar, POA, Bank, Declarations)
   - Document verification workflow
   - File metadata tracking (size, MIME type, upload user)

3. **Address Management**
   - Separate model for addresses (no address fields on application)
   - Support for CURRENT and PERMANENT address types
   - Proof of Address (POA) code mapping (POA01-POA25)
   - Optional geolocation support (latitude/longitude)

4. **Family Member Management**
   - Track all household members including applicant (as SELF)
   - Aadhaar deduplication support
   - Age calculation and validation
   - Relationship tracking

5. **Audit & Compliance**
   - Complete audit trail of all changes
   - User tracking (submitted_by, verified_by, approved_by)
   - IP address logging
   - JSON field for change tracking

---

## 🏗️ Architecture

### Core Models

```
UjjwalaV3Application (Main)
    ├── UjjwalaV3Address (1:N)
    │   ├── CURRENT (1:1 required)
    │   └── PERMANENT (1:1 required)
    ├── UjjwalaV3FamilyMember (1:N)
    │   └── SELF member (1:1 required, matches applicant)
    ├── UjjwalaV3Document (1:N)
    │   ├── Linked to Application
    │   ├── Optionally linked to FamilyMember (for Aadhaar docs)
    │   └── Optionally linked to Address (for POA docs)
    └── UjjwalaV3AuditLog (1:N)
```

### Technology Stack

- **Backend**: Django 3.2+
- **API**: Django REST Framework
- **Database**: PostgreSQL (recommended) or any Django-supported DB
- **Validation**: Django validators + custom validators
- **Admin**: Django Admin with custom interfaces
- **File Storage**: Django FileField (supports local/S3/MinIO)

---

## 📊 Data Models

### 1. UjjwalaV3Application

Main application model tracking the entire lifecycle.

**Key Fields:**
- Applicant details (name, gender, DOB, Aadhaar, mobile, email)
- Family composition document metadata
- Bank details for DBTL subsidy
- LPG connection type (14.2 KG / 5 KG single / 5 KG double)
- Consents and declarations (7 mandatory fields)
- Status and workflow timestamps
- Verification status tracking

**Constraints:**
- `applicant_gender` must be 'F' (Female)
- `is_migrant` must be True
- All consents must be signed before submission
- Age must be ≥ 18 years

### 2. UjjwalaV3Address

Stores all address information separately.

**Key Fields:**
- address_type (CURRENT, PERMANENT, OTHER)
- Complete address fields (house, floor, building, street, village, block, district, city, state, pincode)
- Landmark and post office
- POA code (POA01-POA25)
- Optional geolocation

**Constraints:**
- Only ONE address per type per application
- Both CURRENT and PERMANENT are required

### 3. UjjwalaV3FamilyMember

Tracks household composition.

**Key Fields:**
- Full name, relation to applicant, gender
- Aadhaar number, DOB
- Age at application (auto-calculated)

**Constraints:**
- Only ONE member with relation = SELF
- SELF member must match applicant's Aadhaar, gender, and DOB

### 4. UjjwalaV3Document

Central document repository.

**Key Fields:**
- doc_type (enumerated)
- file (FileField)
- file_name, file_size, mime_type
- Links to application, family_member (optional), address (optional)
- Verification status and metadata

**Document Types:**
- AADHAAR_FRONT, AADHAAR_BACK
- CURRENT_ADDRESS_POA, PERMANENT_ADDRESS_POA
- FAMILY_COMPOSITION_DOC, MIGRANT_DECLARATION, DEPRIVATION_DECLARATION
- BANK_PROOF, APPLICANT_PHOTO, KITCHEN_PHOTO, APPLICANT_SIGNATURE
- Plus 10+ more types

### 5. UjjwalaV3AuditLog

Immutable audit trail.

**Key Fields:**
- application, action, actor
- changes (JSONField)
- remarks, IP address
- created_at

**Actions tracked:**
- CREATED, UPDATED, SUBMITTED, VERIFIED, APPROVED, REJECTED, CONNECTION_ISSUED, DOCUMENT_VERIFIED

---

## 🚀 Installation

### 1. Add to Django Project

```python
# In settings.py
INSTALLED_APPS = [
    # ... other apps
    'rest_framework',
    'django_filters',
    'ujjwala_v3',
]
```

### 2. Configure URLs

```python
# In main urls.py
from django.urls import path, include

urlpatterns = [
    # ... other patterns
    path('api/ujjwala-v3/', include('ujjwala_v3.urls')),
]
```

### 3. Run Migrations

```bash
python manage.py makemigrations ujjwala_v3
python manage.py migrate ujjwala_v3
```

### 4. Create Superuser (if needed)

```bash
python manage.py createsuperuser
```

---

## 📝 Usage

### Creating an Application

```python
from ujjwala_v3.models import UjjwalaV3Application, UjjwalaV3Address, UjjwalaV3FamilyMember
from ujjwala_v3.enums import Gender, Caste, LPGConnectionType, AddressType, RelationToApplicant
from datetime import date

# Create application
app = UjjwalaV3Application.objects.create(
    applicant_full_name='Sunita Devi',
    applicant_first_name='Sunita',
    applicant_last_name='Devi',
    applicant_gender=Gender.FEMALE,
    applicant_dob=date(1985, 5, 15),
    applicant_aadhaar_number='123456789012',
    applicant_mobile='9876543210',
    caste=Caste.SC,
    is_migrant=True,
    bank_account_name='Sunita Devi',
    bank_name='State Bank of India',
    bank_branch='Delhi Main',
    bank_ifsc='SBIN0001234',
    bank_account_number='12345678901234',
    lpg_connection_type=LPGConnectionType.SINGLE_14_2KG,
    # Set all consents
    aadhaar_consent_signed=True,
    agrees_to_dbtl=True,
    agrees_pre_installation_check=True,
    agrees_mandatory_inspections=True,
    declares_no_existing_lpg_or_png_connection=True,
    declares_use_for_domestic_cooking_only=True,
    consent_data_sharing_omc_bank=True,
)

# Add current address
current_addr = UjjwalaV3Address.objects.create(
    application=app,
    address_type=AddressType.CURRENT,
    house_flat_no='123',
    city_town='Delhi',
    district='New Delhi',
    state='DL',
    pincode='110001',
    poa_code='POA01',
)

# Add permanent address
permanent_addr = UjjwalaV3Address.objects.create(
    application=app,
    address_type=AddressType.PERMANENT,
    house_flat_no='456',
    city_town='Patna',
    district='Patna',
    state='BR',
    pincode='800001',
    poa_code='POA09',
)

# Add applicant as SELF family member
self_member = UjjwalaV3FamilyMember.objects.create(
    application=app,
    full_name='Sunita Devi',
    relation_to_applicant=RelationToApplicant.SELF,
    gender=Gender.FEMALE,
    aadhaar_number='123456789012',
    dob=date(1985, 5, 15),
)
```

---

## 🔌 API Documentation

### Base URL
```
http://your-domain.com/api/ujjwala-v3/
```

### Authentication
Configure DRF authentication in settings.py:
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

### Endpoints

#### Applications

**List Applications**
```
GET /api/ujjwala-v3/applications/
```

Query Parameters:
- `status`: Filter by status (can be multiple)
- `caste`: Filter by caste
- `mobile`: Filter by mobile number
- `aadhaar`: Filter by Aadhaar number
- `created_after`: Filter by creation date
- `search`: Search in name, mobile, application number

**Create Application**
```
POST /api/ujjwala-v3/applications/
Content-Type: application/json

{
  "applicant_full_name": "Sunita Devi",
  "applicant_first_name": "Sunita",
  "applicant_last_name": "Devi",
  "applicant_gender": "F",
  "applicant_dob": "1985-05-15",
  "applicant_aadhaar_number": "123456789012",
  "applicant_mobile": "9876543210",
  "caste": "SC",
  "is_migrant": true,
  "bank_account_name": "Sunita Devi",
  "bank_name": "State Bank of India",
  "bank_branch": "Delhi Main",
  "bank_ifsc": "SBIN0001234",
  "bank_account_number": "12345678901234",
  "lpg_connection_type": "SINGLE_14_2KG",
  "aadhaar_consent_signed": true,
  "agrees_to_dbtl": true,
  "agrees_pre_installation_check": true,
  "agrees_mandatory_inspections": true,
  "declares_no_existing_lpg_or_png_connection": true,
  "declares_use_for_domestic_cooking_only": true,
  "consent_data_sharing_omc_bank": true,
  "addresses": [
    {
      "address_type": "CURRENT",
      "house_flat_no": "123",
      "city_town": "Delhi",
      "district": "New Delhi",
      "state": "DL",
      "pincode": "110001",
      "poa_code": "POA01"
    },
    {
      "address_type": "PERMANENT",
      "house_flat_no": "456",
      "city_town": "Patna",
      "district": "Patna",
      "state": "BR",
      "pincode": "800001",
      "poa_code": "POA09"
    }
  ],
  "family_members": [
    {
      "full_name": "Sunita Devi",
      "relation_to_applicant": "SELF",
      "gender": "F",
      "aadhaar_number": "123456789012",
      "dob": "1985-05-15"
    }
  ]
}
```

**Submit Application**
```
POST /api/ujjwala-v3/applications/{id}/submit/
Content-Type: application/json

{
  "remarks": "Application ready for submission"
}
```

**Approve Application**
```
POST /api/ujjwala-v3/applications/{id}/approve/
Content-Type: application/json

{
  "action": "APPROVE",
  "remarks": "All documents verified and approved"
}
```

**Reject Application**
```
POST /api/ujjwala-v3/applications/{id}/reject/
Content-Type: application/json

{
  "action": "REJECT",
  "remarks": "Incomplete documentation",
  "rejection_reason": "Bank proof document is not clear"
}
```

**Get Statistics**
```
GET /api/ujjwala-v3/applications/statistics/
```

Response:
```json
{
  "total": 1250,
  "by_status": {
    "DRAFT": 50,
    "SUBMITTED": 200,
    "UNDER_VERIFICATION": 300,
    "APPROVED": 600,
    "CONNECTION_ISSUED": 100
  },
  "by_caste": {
    "SC": 400,
    "ST": 300,
    "OBC": 400,
    "GENERAL": 150
  },
  "submitted_today": 15,
  "approved_this_month": 120
}
```

#### Documents

**Upload Document**
```
POST /api/ujjwala-v3/documents/
Content-Type: multipart/form-data

application: {application_id}
doc_type: AADHAAR_FRONT
family_member: {family_member_id}
file: {file_upload}
description: Applicant Aadhaar front side
```

**Verify Document**
```
POST /api/ujjwala-v3/documents/{id}/verify/
Content-Type: application/json

{
  "remarks": "Document verified successfully"
}
```

---

## 🎨 Admin Interface

Access Django admin at `/admin/`

### Features

- **Application Admin**:
  - Inline editing of addresses, family members, documents
  - Color-coded status badges
  - Bulk actions (submit, verify, approve)
  - Advanced filtering by status, caste, dates
  - Search by name, mobile, Aadhaar, application number

- **Document Admin**:
  - Image preview for uploaded documents
  - File size display in human-readable format
  - Verification workflow
  - Bulk verification

- **Audit Log Admin**:
  - Read-only access
  - Complete audit trail
  - Filter by action and date

---

## ⚖️ Business Rules

### Hard Requirements (ENFORCED)

1. **Applicant Gender**: MUST be Female ('F')
   - Enforced via database constraint
   - Validated in model clean() method
   - Validated in serializer

2. **Migration Status**: is_migrant MUST be True
   - Enforced via database constraint
   - Validated in model and serializer

3. **Age Requirement**: Applicant MUST be ≥ 18 years
   - Validated via custom validator
   - Calculated from DOB

4. **Document Storage**: NO FileField/ImageField on Application/Address/FamilyMember
   - All files stored in UjjwalaV3Document model

5. **Address Storage**: NO address fields on Application
   - All address data in UjjwalaV3Address model

### Application Completion Requirements

An application is considered complete when:
- ✅ Has CURRENT address
- ✅ Has PERMANENT address
- ✅ Has SELF family member (matching applicant)
- ✅ Has required documents:
  - AADHAAR_FRONT
  - AADHAAR_BACK
  - BANK_PROOF
  - MIGRANT_DECLARATION

### Workflow Rules

1. **DRAFT → SUBMITTED**:
   - All mandatory consents must be signed
   - Application must be complete
   - Generates application_number

2. **SUBMITTED → UNDER_VERIFICATION**:
   - Only authorized users
   - Records verified_by and verified_at

3. **UNDER_VERIFICATION → APPROVED**:
   - Requires approval remarks
   - Records approved_by and approved_at

4. **Any Status → REJECTED**:
   - Requires rejection_reason
   - Can be rejected from any status

5. **APPROVED → CONNECTION_ISSUED**:
   - Final step
   - Records connection_issued_at

---

## 🧪 Testing

### Run Tests

```bash
python manage.py test ujjwala_v3
```

### Example Test

```python
from django.test import TestCase
from ujjwala_v3.models import UjjwalaV3Application
from ujjwala_v3.enums import Gender, ApplicationStatus
from datetime import date

class ApplicationTestCase(TestCase):
    def test_create_application(self):
        app = UjjwalaV3Application.objects.create(
            applicant_full_name='Test User',
            applicant_first_name='Test',
            applicant_last_name='User',
            applicant_gender=Gender.FEMALE,
            applicant_dob=date(1990, 1, 1),
            applicant_aadhaar_number='123456789012',
            applicant_mobile='9876543210',
            # ... other required fields
        )

        self.assertEqual(app.status, ApplicationStatus.DRAFT)
        self.assertTrue(app.is_migrant)
        self.assertGreaterEqual(app.applicant_age, 18)
```

---

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [PMUY Official Guidelines](https://pmuy.gov.in/)

---

## 🤝 Contributing

This is production code. For modifications:

1. Write comprehensive tests
2. Update documentation
3. Follow Django coding standards
4. Maintain backward compatibility

---

## 📄 License

Proprietary - All rights reserved.

---

## 👤 Author

Senior Backend Engineer
Designed for production use in government LPG distribution systems.
