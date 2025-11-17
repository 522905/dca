# Ujjwala V3 - FSM (Finite State Machine) Implementation

## Overview

The Ujjwala V3 application uses **django-fsm** to enforce strict state transitions with comprehensive validation. This ensures data integrity and compliance with PMUY business rules.

---

## State Diagram

```
┌─────────┐
│  DRAFT  │ ◄── Initial state (applicant filling form)
└────┬────┘
     │
     │ submit()
     │ ✓ Female applicant (gender = F)
     │ ✓ Age >= 18 years
     │ ✓ All 7 consents signed
     │ ✓ CURRENT + PERMANENT addresses
     │ ✓ Different states (migrant verification)
     │ ✓ SELF family member matching applicant
     │ ✓ All family members have Aadhaar docs
     │ ✓ 6 required documents uploaded
     │ ✓ LPG connection type specified
     ▼
┌────────────┐
│ SUBMITTED  │ ◄── Application submitted for review
└────┬───────┘
     │
     │ start_verification()
     │ ✓ No additional validation
     ▼
┌──────────────────────┐
│ UNDER_VERIFICATION   │ ◄── Verification in progress
└──────┬───────────────┘
       │
       │ approve()                      reject(reason)
       │ ✓ Aadhaar verified             ✓ Rejection reason required
       │ ✓ Bank verified                │
       │ ✓ Address verified             │
       ▼                                 ▼
┌──────────┐                    ┌──────────┐
│ APPROVED │                    │ REJECTED │ ◄── Terminal state
└────┬─────┘                    └──────────┘
     │
     │ issue_connection()
     │ ✓ From APPROVED only
     ▼
┌────────────────────┐
│ CONNECTION_ISSUED  │ ◄── Terminal state (success)
└────────────────────┘
```

---

## FSM Transitions

### 1. submit()
**Transition**: `DRAFT` → `SUBMITTED`

**Purpose**: Submit application for official review

**Validations** (All must pass):
1. **Applicant Gender**: Must be Female (F)
2. **Applicant Age**: Must be >= 18 years
3. **All Consents Signed** (7 mandatory):
   - `aadhaar_consent_signed`
   - `agrees_to_dbtl`
   - `agrees_pre_installation_check`
   - `agrees_mandatory_inspections`
   - `declares_no_existing_lpg_or_png_connection`
   - `declares_use_for_domestic_cooking_only`
   - `consent_data_sharing_omc_bank`

4. **Addresses** (both required):
   - CURRENT address exists
   - PERMANENT address exists
   - **Migrant Rule**: CURRENT.state ≠ PERMANENT.state

5. **Family Members**:
   - SELF member exists
   - SELF.aadhaar_number == applicant.aadhaar_number
   - SELF.dob == applicant.dob
   - SELF.gender == applicant.gender
   - Each family member has Aadhaar front + back documents
   - No duplicate Aadhaar numbers within application

6. **Required Documents** (6 total):
   - CURRENT_ADDRESS_POA
   - PERMANENT_ADDRESS_POA
   - FAMILY_COMPOSITION_DOC
   - DEPRIVATION_DECLARATION
   - BANK_PROOF
   - MIGRANT_DECLARATION

7. **LPG Connection Type**: Must be specified

**Side Effects**:
- Generates `application_number` (format: UJJV3-YYYY-XXXXXXXX)
- Sets `submitted_at` timestamp
- Sets `submitted_by` user

**Example**:
```python
try:
    application.submit(user=request.user)
    application.save()
except ValidationError as e:
    # Handle validation error
    print(f"Submission failed: {e}")
```

---

### 2. start_verification()
**Transition**: `SUBMITTED` → `UNDER_VERIFICATION`

**Purpose**: Begin formal verification process

**Validations**: None (administrative action)

**Side Effects**:
- Sets `verification_started_at` timestamp
- Sets `verified_by` user

**Example**:
```python
application.start_verification(user=request.user)
application.save()
```

---

### 3. approve()
**Transition**: `UNDER_VERIFICATION` → `APPROVED`

**Purpose**: Approve application after all verifications complete

**Validations**:
1. `aadhaar_verification_status` == `VERIFIED`
2. `bank_verification_status` == `VERIFIED`
3. `address_verification_status` == `VERIFIED`

**Side Effects**:
- Sets `approved_at` timestamp
- Sets `verified_at` timestamp
- Sets `approved_by` user

**Example**:
```python
# First, update verification statuses
application.aadhaar_verification_status = VerificationStatus.VERIFIED
application.bank_verification_status = VerificationStatus.VERIFIED
application.address_verification_status = VerificationStatus.VERIFIED
application.save()

# Then approve
try:
    application.approve(user=request.user)
    application.save()
except ValidationError as e:
    print(f"Approval failed: {e}")
```

---

### 4. reject()
**Transition**: `SUBMITTED` | `UNDER_VERIFICATION` | `VERIFICATION_FAILED` → `REJECTED`

**Purpose**: Reject application with reason

**Validations**:
1. `reason` parameter is required and non-empty

**Parameters**:
- `reason` (string, required): Reason for rejection
- `user` (User, optional): User performing rejection

**Side Effects**:
- Sets `rejection_reason` field
- Sets `rejected_at` timestamp
- Sets `verified_by` user (rejects user)

**Example**:
```python
application.reject(
    reason="Aadhaar verification failed - name mismatch",
    user=request.user
)
application.save()
```

---

### 5. issue_connection()
**Transition**: `APPROVED` → `CONNECTION_ISSUED`

**Purpose**: Final step - issue LPG connection

**Validations**: None (only possible from APPROVED status)

**Side Effects**:
- Sets `connection_issued_at` timestamp

**Example**:
```python
application.issue_connection(user=request.user)
application.save()
```

---

## Business Rules Enforcement

### Rule 1: Female Adult Applicant
```python
# Enforced at multiple levels:
# 1. Database constraint
CheckConstraint(check=Q(applicant_gender=Gender.FEMALE))

# 2. Model clean()
if self.applicant_gender != Gender.FEMALE:
    raise ValidationError("Applicant must be female")

# 3. FSM submit() transition
if self.applicant_gender != Gender.FEMALE:
    raise ValidationError("Applicant must be female")

# 4. Age validation
if self.applicant_age < 18:
    raise ValidationError("Applicant must be at least 18 years old")
```

### Rule 2: Migrant Status
```python
# Enforced at multiple levels:
# 1. Database constraint
CheckConstraint(check=Q(is_migrant=True))

# 2. FSM submit() transition
if not self.is_migrant:
    raise ValidationError("Application must be for migrant households")

# 3. Address state difference
if current_addr.state == permanent_addr.state:
    raise ValidationError(
        "For migrant applications, CURRENT and PERMANENT addresses "
        "must be in different states"
    )
```

### Rule 3: Family Member SELF Validation
```python
# SELF member must match applicant exactly
if self_member.aadhaar_number != self.applicant_aadhaar_number:
    raise ValidationError("SELF member Aadhaar must match applicant")

if self_member.dob != self.applicant_dob:
    raise ValidationError("SELF member DOB must match applicant")

if self_member.gender != self.applicant_gender:
    raise ValidationError("SELF member gender must match applicant")
```

### Rule 4: Aadhaar Documents for All Family Members
```python
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
```

### Rule 5: No Duplicate Aadhaar Within Application
```python
aadhaar_numbers = list(
    self.family_members.values_list('aadhaar_number', flat=True)
)
if len(aadhaar_numbers) != len(set(aadhaar_numbers)):
    raise ValidationError("Duplicate Aadhaar numbers found in family members")
```

---

## REST API Integration

### Submit Application
```http
POST /api/ujjwala-v3/applications/{id}/submit/
Content-Type: application/json

{
  "remarks": "All documents verified and complete"
}
```

**Response (Success)**:
```json
{
  "id": "uuid",
  "application_number": "UJJV3-2024-00001234",
  "status": "SUBMITTED",
  "submitted_at": "2024-11-17T12:00:00Z",
  ...
}
```

**Response (Validation Error)**:
```json
{
  "error": "Missing required documents: CURRENT_ADDRESS_POA, BANK_PROOF"
}
```

### Start Verification
```http
POST /api/ujjwala-v3/applications/{id}/start_verification/
Content-Type: application/json

{
  "remarks": "Beginning verification process"
}
```

### Approve Application
```http
POST /api/ujjwala-v3/applications/{id}/approve/
Content-Type: application/json

{
  "action": "APPROVE",
  "remarks": "All verifications completed successfully"
}
```

**Note**: Will fail if any verification status is not VERIFIED.

### Reject Application
```http
POST /api/ujjwala-v3/applications/{id}/reject/
Content-Type: application/json

{
  "action": "REJECT",
  "remarks": "Unable to verify documents",
  "rejection_reason": "Aadhaar photo quality too poor for verification"
}
```

### Issue Connection
```http
POST /api/ujjwala-v3/applications/{id}/issue_connection/
Content-Type: application/json

{
  "remarks": "LPG connection issued on 2024-11-17"
}
```

---

## Error Handling

### FSM Transition Errors

When a transition fails, django-fsm raises `ValidationError`:

```python
from django.core.exceptions import ValidationError

try:
    application.submit(user=request.user)
    application.save()
except ValidationError as e:
    # e.message contains detailed error
    return Response({'error': str(e)}, status=400)
```

### Common Validation Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| "Applicant must be female" | Gender is not F | Update gender to F |
| "Applicant must be at least 18 years old" | Age < 18 | Verify DOB is correct |
| "All mandatory consents must be signed" | Missing consent | Sign all 7 consents |
| "CURRENT address is required" | No current address | Add CURRENT address |
| "PERMANENT address is required" | No permanent address | Add PERMANENT address |
| "For migrant applications, CURRENT and PERMANENT addresses must be in different states" | Same state | Update one address to different state |
| "Applicant must be added as SELF family member" | No SELF member | Add applicant as SELF member |
| "SELF member Aadhaar must match applicant Aadhaar" | Mismatch | Fix Aadhaar number |
| "Family member X missing Aadhaar documents" | Missing docs | Upload Aadhaar front + back |
| "Duplicate Aadhaar numbers found" | Duplicate | Remove duplicate entry |
| "Missing required documents: X, Y, Z" | Documents missing | Upload all 6 required docs |
| "Aadhaar verification must be completed before approval" | Not verified | Complete Aadhaar verification |

---

## Testing FSM Transitions

### Unit Test Example

```python
from django.test import TestCase
from django.core.exceptions import ValidationError
from ujjwala_v3.models import UjjwalaV3Application
from ujjwala_v3.enums import ApplicationStatus, Gender

class FSMTransitionTestCase(TestCase):
    def setUp(self):
        # Create a complete application
        self.app = create_complete_application()

    def test_submit_transition(self):
        """Test DRAFT → SUBMITTED transition"""
        self.assertEqual(self.app.status, ApplicationStatus.DRAFT)

        # Submit should succeed
        self.app.submit()
        self.app.save()

        self.assertEqual(self.app.status, ApplicationStatus.SUBMITTED)
        self.assertIsNotNone(self.app.submitted_at)
        self.assertIsNotNone(self.app.application_number)

    def test_submit_fails_without_consents(self):
        """Test submit fails without all consents"""
        self.app.aadhaar_consent_signed = False

        with self.assertRaises(ValidationError):
            self.app.submit()

    def test_approve_requires_verifications(self):
        """Test approve fails without verifications"""
        self.app.submit()
        self.app.start_verification()
        self.app.save()

        # Try to approve without verifications
        with self.assertRaises(ValidationError) as context:
            self.app.approve()

        self.assertIn("Aadhaar verification", str(context.exception))
```

---

## Monitoring & Audit

### Audit Logs

Every FSM transition creates an audit log entry:

```python
UjjwalaV3AuditLog.objects.create(
    application=application,
    action='SUBMITTED',  # or VERIFICATION_STARTED, APPROVED, REJECTED, etc.
    actor=request.user,
    remarks='User remarks here',
    ip_address='192.168.1.1'
)
```

### Query Applications by Status

```python
# Get all submitted applications
submitted = UjjwalaV3Application.objects.filter(
    status=ApplicationStatus.SUBMITTED
)

# Get all approved in last 30 days
from datetime import timedelta
from django.utils import timezone

recent_approved = UjjwalaV3Application.objects.filter(
    status=ApplicationStatus.APPROVED,
    approved_at__gte=timezone.now() - timedelta(days=30)
)
```

---

## Best Practices

### 1. Always Use FSM Transitions
❌ **DON'T**:
```python
application.status = ApplicationStatus.SUBMITTED  # Bypasses validation!
application.save()
```

✅ **DO**:
```python
application.submit(user=request.user)
application.save()
```

### 2. Handle ValidationErrors
```python
try:
    application.submit(user=request.user)
    application.save()
except ValidationError as e:
    # Log error
    logger.error(f"Submission failed: {e}")
    # Notify user
    return Response({'error': str(e)}, status=400)
```

### 3. Check Available Transitions
```python
# Get all possible transitions from current state
available = application.get_available_status_transitions()

# Check if specific transition is available
can_submit = application.can_submit()
can_approve = application.can_approve()
```

### 4. Atomic Operations
```python
from django.db import transaction

with transaction.atomic():
    application.approve(user=request.user)
    application.save()

    # Create notification
    send_approval_email(application)

    # Update related records
    # ...
```

---

## Summary

- ✅ **5 FSM Transitions**: submit, start_verification, approve, reject, issue_connection
- ✅ **Comprehensive Validation**: All business rules enforced at transition time
- ✅ **Protected State**: Cannot bypass FSM using direct assignment
- ✅ **Audit Trail**: Every transition logged with user/timestamp/remarks
- ✅ **Type Safety**: django-fsm prevents invalid transitions
- ✅ **Production-Ready**: Tested, validated, enterprise-grade implementation

---

**For More Information**:
- django-fsm documentation: https://github.com/viewflow/django-fsm
- Ujjwala V3 README: `/home/user/dca/ujjwala_v3/README.md`
- Integration Guide: `/home/user/dca/ujjwala_v3/INTEGRATION.md`
