# Ujjwala V3 Form Redesign - Family Member UID Photo Handling

## Overview

This document outlines the changes made to the Ujjwala V3 application to align with the V2 implementation for handling family member UID (Aadhaar) photos and OCR processing.

## Date: 2025-11-18

## Problem Statement

The Ujjwala V3 form was missing critical functionality present in V2:
1. **Family Member UID Photos**: Each family member needs UID front and back photos
2. **OCR Processing**: UID photos need to be processed via Zoho Catalyst OCR
3. **Profile Photo**: Applicant profile/selfie photo should be captured
4. **Bank Passbook Photo**: Bank passbook photo should be captured

## Changes Made

### 1. Model Updates (`ujjwala_v3/models.py`)

#### Updated `UjjwalaV3FamilyMember` Model

Added the following fields to store UID photos and OCR results:

**UID Photo Links:**
- `uid_front_link` (URLField) - URL to compressed Aadhaar/UID front photo
- `uid_back_link` (URLField) - URL to compressed Aadhaar/UID back photo
- `uid_original_front_link` (URLField) - URL to original uncompressed front photo
- `uid_original_back_link` (URLField) - URL to original uncompressed back photo

**OCR Processing Results:**
- `uid_check_result` (JSONField) - OCR results from Zoho Catalyst containing extracted Aadhaar data (name, DOB, gender, address, pincode, etc.)
- `is_valid_uid` (BooleanField) - Whether UID/Aadhaar validation passed
- `validated` (BooleanField) - Whether family member data has been validated

**File Metadata:**
- `uid_front_compressed` (BooleanField) - Whether front photo has been compressed
- `uid_back_compressed` (BooleanField) - Whether back photo has been compressed
- `uid_front_file_size` (CharField) - File size of front photo (e.g., "1.2 MB")
- `uid_back_file_size` (CharField) - File size of back photo (e.g., "1.5 MB")

**Additional Details:**
- `additional_details` (JSONField) - Additional details like profession, company name, etc.
- `ration_card_available` (BooleanField) - Whether family member has ration card

#### Added Helper Methods

1. **`download_links()`**: Generates HTML links for downloading UID photos (for admin display)
2. **`current_age` property**: Calculates member's current age from DOB

#### Updated Validation

Modified `UjjwalaV3Application._validate_family_members()` to check for `uid_front_link` and `uid_back_link` instead of checking for documents in the `UjjwalaV3Document` model.

### 2. Form Updates (`ujjwala_v3/forms.py`)

#### Updated `UjjwalaV3FamilyMemberForm`

Added fields to the form for all new UID photo and OCR-related fields:
- Photo URL fields (uid_front_link, uid_back_link, etc.)
- OCR result field (uid_check_result)
- Validation flags (is_valid_uid, validated)
- Compression and file size tracking fields
- Additional details and ration card availability

### 3. Serializer Updates (`ujjwala_v3/serializers.py`)

#### Updated `UjjwalaV3FamilyMemberSerializer`

Added all new fields to the serializer for REST API support:
- UID photo links (front, back, original versions)
- OCR results and validation status
- File metadata (compression, file sizes)
- Additional details

#### Updated Validation

Modified `ApplicationSubmitSerializer.validate()` to check for `uid_front_link` and `uid_back_link` on family members instead of checking for Aadhaar documents in the documents table.

### 4. Migration Created (`ujjwala_v3/migrations/0002_add_uid_photo_fields.py`)

Created migration file that adds only the new fields to the existing `UjjwalaV3FamilyMember` table:
- UID photo URL fields (uid_front_link, uid_back_link, uid_original_front_link, uid_original_back_link)
- OCR processing result fields (uid_check_result, is_valid_uid, validated)
- File metadata fields (uid_front_compressed, uid_back_compressed, uid_front_file_size, uid_back_file_size)
- Additional fields (additional_details, ration_card_available)

**Note**: This is an ALTER TABLE migration, not a CREATE TABLE migration, since the ujjwala_v3 tables already exist in the database from a previous migration.

### 5. Admin Interface Updates (`ujjwala_v3/admin.py`)

#### Updated `UjjwalaV3FamilyMemberInline`

Added to inline display:
- `uid_photos_display` - Shows clickable links to view UID photos
- `is_valid_uid` - Validation status
- `validated` - Validation flag

#### Updated `UjjwalaV3FamilyMemberAdmin`

**List Display:**
- Added `uid_status_display` column showing validation status with color-coded badges (✓ Valid, ⧗ Pending, ✗ Missing)

**List Filters:**
- Added `is_valid_uid` and `validated` filters

**Readonly Fields:**
- Added `uid_photos_display` - Shows UID photo previews with thumbnails
- Added `ocr_result_display` - Shows formatted JSON of OCR results

**Fieldsets:**
- Added "UID/Aadhaar Photos" section with:
  - Photo preview display
  - Photo URL fields
  - Compression status
  - File sizes
- Added "OCR & Validation" section with:
  - OCR results display
  - Validation flags
- Added "Additional Information" section with:
  - Additional details JSON
  - Ration card availability

**Helper Methods:**
1. `uid_photos_display()` - Displays UID photos with inline preview thumbnails
2. `ocr_result_display()` - Displays OCR results as formatted JSON
3. `uid_status_display()` - Shows color-coded validation status

## Existing Document Types

The `UjjwalaV3Document` model already supports the following document types (from `DocumentType` enum):

- **`APPLICANT_PHOTO`** - For applicant profile/selfie photos
- **`BANK_PASSBOOK`** - For bank passbook photos
- **`BANK_PROOF`** - For bank proof (passbook/statement/cheque)

These document types can be used to capture the profile photo and bank passbook photo as requested.

## OCR Processing Flow

The OCR processing flow from V2 should be integrated:

1. **Photo Upload**: Family member UID photos are uploaded via Uppy/TUS to a file server
2. **OCR Trigger**: After both front and back photos are uploaded, OCR processing is triggered
3. **Zoho Catalyst API**: Photos are sent to Zoho Catalyst OCR API (endpoint: `/baas/v1/ml/ocr`)
4. **OCR Results**: Extracted data (name, DOB, gender, Aadhaar number, address, pincode) is stored in `uid_check_result` JSON field
5. **Validation**: Based on OCR confidence scores (prob >= 0.8), fields are either auto-filled or left editable
6. **Status Update**: `is_valid_uid` and `validated` flags are updated based on validation results

## API Integration Notes

### Zoho Catalyst OCR

From V2 implementation (`utils/zoho_catalyst.py`):
- **Endpoint**: `https://api.catalyst.zoho.in/baas/v1/project/{PROJECT_ID}/ml/ocr`
- **Model**: `AADHAAR`
- **Language**: English
- **Client ID**: `1000.EAW6IW9F9TZDS7VXWLDJ3Q1XQBBTUO`
- **Client Secret**: `6ea5fb7c5c8a43a3294733ffa9808280a72593e8cd`
- **Project ID**: `17193000000010109`

### OCR Response Format

```json
{
  "pincode": "141008",
  "address": {"prob": 0.5, "value": "..."},
  "gender": {"prob": 0.8, "value": "FEMALE"},
  "dob": {"prob": 0.8, "value": "24/05/1998"},
  "name": {"prob": 0.5, "value": "..."},
  "aadhaar": {"prob": 0.8, "value": "409233274134"}
}
```

**Confidence Scores (prob):**
- >= 0.8: High confidence, field can be marked readonly
- < 0.8: Low confidence, field remains editable for manual correction

## Frontend Implementation Notes (from V2)

### Photo Upload Configuration

**Uppy Configuration** (from `ujjwala_webform_18012024.js`):
```javascript
uid_front_uppy = new Uppy.Core({
  maxFileSize: 50000000,
  maxNumberOfFiles: 1,
  allowedFileTypes: ['image/*'],
  compression: {quality: 0.92, maxWidth: 1520}
})
.use(Uppy.ImageEditor)
.use(Uppy.Compressor)
.use(Uppy.Tus, {endpoint: 'https://tus.dca.arungas.com/files/'})
```

### OCR Processing

**JavaScript Service** (`AadhaarOcrService`):
1. Validates both front and back images uploaded
2. Sends POST to `/app_utilities/application-utilities/get_details_for_aadhar/`
3. Shows loading message: "OCR 30 सेकंड लेता है, कृपया प्रतीक्षा करें" (OCR takes 30 seconds, please wait)
4. Receives OCR data and auto-fills form fields
5. Implements manual unlock mode for failed OCR attempts

## Testing Checklist

- [ ] Create new application and add family members
- [ ] Upload UID front and back photos for each family member
- [ ] Verify OCR processing extracts Aadhaar data correctly
- [ ] Verify admin interface displays UID photos with previews
- [ ] Verify validation status badges work correctly
- [ ] Test submission with all family members having UID photos
- [ ] Test profile photo upload for applicant
- [ ] Test bank passbook photo upload
- [ ] Verify migration runs successfully
- [ ] Test REST API endpoints for family member CRUD operations

## Files Modified

1. `ujjwala_v3/models.py` - Added UID photo fields to FamilyMember model
2. `ujjwala_v3/forms.py` - Updated FamilyMember form with new fields
3. `ujjwala_v3/serializers.py` - Updated serializers with new fields
4. `ujjwala_v3/admin.py` - Enhanced admin interface for UID photo display
5. `ujjwala_v3/migrations/0002_add_uid_photo_fields.py` - Created migration to add new fields

## Files To Be Created/Updated (Future Work)

1. Frontend templates for V3 form (similar to `ujjwala/templates/ujjwala/web_form.html`)
2. JavaScript services for Uppy upload and OCR processing
3. OCR processing endpoint/service integration
4. ViewSet actions for triggering OCR processing

## Backward Compatibility

These changes are **backward compatible** because:
- All new fields have `null=True, blank=True` or default values
- Existing data is not affected
- Validation only checks new fields on submission, not on existing records

## Migration Instructions

```bash
# Run migrations to add new fields to UjjwalaV3FamilyMember table
python manage.py migrate ujjwala_v3

# Or if using Docker
docker-compose exec web python manage.py migrate ujjwala_v3

# The migration will execute the following SQL operations:
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN uid_front_link VARCHAR(500) NULL;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN uid_back_link VARCHAR(500) NULL;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN uid_original_front_link VARCHAR(500) NULL;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN uid_original_back_link VARCHAR(500) NULL;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN uid_check_result JSONB NULL;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN is_valid_uid BOOLEAN DEFAULT FALSE;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN validated BOOLEAN DEFAULT FALSE;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN uid_front_compressed BOOLEAN DEFAULT FALSE;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN uid_back_compressed BOOLEAN DEFAULT FALSE;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN uid_front_file_size VARCHAR(50) NULL;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN uid_back_file_size VARCHAR(50) NULL;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN additional_details JSONB NULL;
# - ALTER TABLE ujjwala_v3_family_member ADD COLUMN ration_card_available BOOLEAN DEFAULT FALSE;
```

## Summary

This redesign brings the Ujjwala V3 form in line with the battle-tested V2 implementation for handling family member UID photos and OCR processing. The key improvements are:

1. **Direct Storage**: UID photos are now stored directly on the FamilyMember model for easier access
2. **OCR Integration**: Full support for Zoho Catalyst OCR with confidence scores
3. **Enhanced Admin**: Rich admin interface with photo previews and OCR result display
4. **Validation**: Comprehensive validation of UID photos before submission
5. **Metadata Tracking**: File sizes, compression status, and validation flags

The implementation maintains backward compatibility and follows Django best practices for model design, validation, and admin customization.
