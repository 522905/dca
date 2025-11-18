# Ujjwala V3 Frontend Integration Guide
## Photo Upload and OCR Processing

This guide explains how to integrate the new photo upload functionality (Profile Photo, Bank Passbook, and Family Member UID Photos with OCR) into the existing Ujjwala V3 application form.

## Overview

The frontend enhancements add four key features:
1. **Profile Photo Upload** - Applicant's profile photo/selfie
2. **Bank Passbook Photo Upload** - Bank account verification
3. **Family Member UID Photo Upload** - Aadhaar front/back for each family member
4. **OCR Processing** - Automatic data extraction from Aadhaar cards

## Files Created

### JavaScript Files

1. **`/static/js/photo_upload_manager.js`**
   - Main PhotoUploadManager class
   - Handles all photo uploads using Uppy
   - Processes OCR for family member UIDs
   - Manages upload state and data

2. **`/static/js/family_member_manager.js`**
   - Family member creation with UID uploaders
   - Form validation
   - Data collection for submission

### HTML Snippets

1. **`/templates/ujjwala_v3/snippets/profile_photo_section.html`**
   - Profile photo upload section
   - To be inserted in Section 1 (Applicant Details)

2. **`/templates/ujjwala_v3/snippets/bank_passbook_section.html`**
   - Bank passbook photo upload section
   - To be inserted in Section 4 (Bank Details)

3. **`/templates/ujjwala_v3/snippets/family_member_with_uid_photos.html`**
   - Enhanced family member card with UID uploaders
   - Template for dynamically created family members

## Integration Steps

### Step 1: Add JavaScript Files to Template

Add these script tags at the bottom of `/templates/ujjwala_v3/application_form.html`, **after** the Uppy library but **before** the existing form JavaScript:

```html
<!-- Uppy File Upload Library -->
<script src="https://releases.transloadit.com/uppy/v2.13.1/uppy.min.js"></script>

<!-- NEW: Photo Upload Manager -->
<script src="{% static 'js/photo_upload_manager.js' %}"></script>
<script src="{% static 'js/family_member_manager.js' %}"></script>

<!-- Existing form JavaScript -->
<script>
    // Your existing code...
</script>
```

### Step 2: Add Profile Photo Section

In **Section 1: Applicant Details**, after the Aadhaar upload section (around line 450), add:

```html
<!-- Existing Aadhaar upload section -->
<div class="form-group">
    <label class="required-field">Aadhaar Card Front Photo</label>
    <!-- ...existing code... -->
</div>

<!-- NEW: Profile Photo Section -->
<div class="form-group">
    <label class="required-field">
        <i class="fas fa-camera"></i> Profile Photo / Selfie (प्रार्थी की फोटो)
    </label>
    <small class="form-text text-muted mb-2">
        Upload a clear photo or selfie of the applicant. This will be used for identity verification.
    </small>
    <div id="profilePhotoUploader"></div>
    <input type="hidden" name="profile_photo_url" id="profilePhotoUrl">
    <div id="profilePhotoPreview"></div>
</div>
```

### Step 3: Add Bank Passbook Photo Section

In **Section 4: Bank Details**, after the IFSC code field (around line 750), add:

```html
<!-- Existing IFSC field -->
<div class="form-group">
    <label class="required-field">IFSC Code</label>
    <input type="text" name="bank_ifsc" class="form-control" required>
</div>

<!-- NEW: Bank Passbook Photo Section -->
<div class="form-group">
    <label class="required-field">
        <i class="fas fa-book"></i> Bank Passbook Photo (पास बुक का विवरण)
    </label>
    <small class="form-text text-muted mb-2">
        Upload a clear photo of your bank passbook showing account holder name, account number, and IFSC code.
    </small>
    <div id="bankPassbookUploader"></div>
    <input type="hidden" name="bank_passbook_url" id="bankPassbookUrl">
    <div id="bankPassbookPreview"></div>
</div>
```

### Step 4: Replace Add Family Member Button Handler

In **Section 6: Family Members**, replace the existing `$('#addFamilyMember').click()` handler with:

```javascript
// OLD CODE (REMOVE):
$('#addFamilyMember').click(function() {
    // Old family member creation code...
});

// NEW CODE (ADD):
// Button binding is now in family_member_manager.js
// Just ensure the button ID is 'addFamilyMember'
```

### Step 5: Update Form Submission

Update the form submission code to include photo URLs and family member data with UID photos:

```javascript
function submitForm() {
    // Validate family members have UID photos
    if (!validateFamilyMembers()) {
        return false;
    }

    // Collect all data
    const formData = {
        // Existing applicant details...
        profile_photo_url: $('#profilePhotoUrl').val(),
        bank_passbook_url: $('#bankPassbookUrl').val(),

        // Family members with UID data
        family_members: collectFamilyMemberData()
    };

    // Submit via AJAX
    $.ajax({
        url: '/ujjwala_v3/apply/',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(formData),
        success: function(response) {
            console.log('Form submitted successfully:', response);
            window.location.href = response.redirect_url;
        },
        error: function(error) {
            console.error('Submission error:', error);
            alert('Failed to submit form. Please try again.');
        }
    });
}
```

### Step 6: Update Views to Handle New Data

Update `/ujjwala_v3/views.py` to handle the new photo URLs and UID data:

```python
def public_application_form(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        # Create application
        application = UjjwalaV3Application.objects.create(
            # ... existing fields ...
        )

        # Save profile photo as document
        if data.get('profile_photo_url'):
            UjjwalaV3Document.objects.create(
                application=application,
                doc_type=DocumentType.APPLICANT_PHOTO,
                file_url=data['profile_photo_url'],
                file_name='profile_photo.jpg'
            )

        # Save bank passbook photo as document
        if data.get('bank_passbook_url'):
            UjjwalaV3Document.objects.create(
                application=application,
                doc_type=DocumentType.BANK_PASSBOOK,
                file_url=data['bank_passbook_url'],
                file_name='bank_passbook.jpg'
            )

        # Create family members with UID data
        for member_data in data.get('family_members', []):
            family_member = UjjwalaV3FamilyMember.objects.create(
                application=application,
                full_name=member_data['name'],
                relation_to_applicant=member_data['relation'],
                gender=member_data['gender'],
                dob=member_data['dob'],
                aadhaar_number=member_data['aadhaar_number'],
                # UID Photo URLs
                uid_front_link=member_data.get('uid_front_link'),
                uid_back_link=member_data.get('uid_back_link'),
                uid_original_front_link=member_data.get('uid_original_front_link'),
                uid_original_back_link=member_data.get('uid_original_back_link'),
                # OCR Results
                uid_check_result=member_data.get('uid_check_result'),
                is_valid_uid=member_data.get('is_valid_uid', False),
                validated=member_data.get('validated', False)
            )

        return JsonResponse({
            'success': True,
            'redirect_url': f'/ujjwala_v3/application-success/{application.application_number}/'
        })
```

## Features Explained

### 1. Profile Photo Upload

- **Location**: Section 1 (Applicant Details)
- **Purpose**: Identity verification
- **File Type**: Images only
- **Max Size**: 10 MB
- **Features**: Image editor, compression (quality 0.9, max 1024x1024)
- **Storage**: Uploaded to TUS server, URL stored in `profile_photo_url` hidden field
- **Database**: Saved as `UjjwalaV3Document` with type `APPLICANT_PHOTO`

### 2. Bank Passbook Photo Upload

- **Location**: Section 4 (Bank Details)
- **Purpose**: Bank account verification
- **File Type**: Images only
- **Max Size**: 10 MB
- **Features**: Image editor, compression (quality 0.9, max 2048x2048)
- **Storage**: Uploaded to TUS server, URL stored in `bank_passbook_url` hidden field
- **Database**: Saved as `UjjwalaV3Document` with type `BANK_PASSBOOK`

### 3. Family Member UID Photos with OCR

- **Location**: Section 6 (Family Members)
- **Purpose**: Identity verification and automatic data extraction
- **File Type**: Images only (both front and back required)
- **Max Size**: 50 MB per photo
- **Features**:
  - Image editor
  - Compression (quality 0.92, max 1520px)
  - **Automatic OCR processing** when both photos uploaded
  - Auto-fill form fields from OCR data
  - Confidence-based field locking (prob >= 0.8)

#### OCR Flow:
1. User uploads UID front photo → Stored in TUS
2. User uploads UID back photo → Stored in TUS
3. **Automatic trigger**: Both photos uploaded → OCR processing starts
4. Loading indicator shown: "Processing OCR... This may take 30 seconds"
5. AJAX POST to `/app_utilities/application-utilities/get_details_for_aadhar/`
6. Zoho Catalyst processes images and returns JSON with:
   - Name (with confidence score)
   - DOB (with confidence score)
   - Gender (with confidence score)
   - Aadhaar number (with confidence score)
   - Address (with confidence score)
7. Form fields auto-filled with OCR data
8. Fields with confidence >= 0.8 are locked (readonly)
9. Fields with confidence < 0.8 remain editable for manual correction
10. Success message shown

#### OCR Data Storage:
- **UID Photo URLs**: `uid_front_link`, `uid_back_link`
- **Original URLs**: `uid_original_front_link`, `uid_original_back_link`
- **OCR Result**: `uid_check_result` (full JSON response from Zoho)
- **Validation Flags**: `is_valid_uid`, `validated`

## Validation Rules

### Profile Photo
- ✅ Required field
- ✅ Must be uploaded before submission
- ✅ Image format only

### Bank Passbook Photo
- ✅ Required field
- ✅ Must be uploaded before submission
- ✅ Image format only

### Family Member UID Photos
- ✅ At least one family member required (SELF - applicant)
- ✅ Each family member must have both front and back UID photos
- ✅ OCR processing is automatic but not blocking (can proceed without OCR success)
- ✅ Manual data entry allowed if OCR fails

## Testing Checklist

### Profile Photo Upload
- [ ] Click upload button and select image
- [ ] Verify image preview displays
- [ ] Check hidden field `profilePhotoUrl` has value
- [ ] Verify image editor works
- [ ] Test compression (check file size reduction)
- [ ] Submit form and verify document saved with type `APPLICANT_PHOTO`

### Bank Passbook Upload
- [ ] Click upload button and select passbook photo
- [ ] Verify image preview displays
- [ ] Check hidden field `bankPassbookUrl` has value
- [ ] Submit form and verify document saved with type `BANK_PASSBOOK`

### Family Member UID Photos
- [ ] Click "Add Family Member" button
- [ ] Verify UID upload sections appear
- [ ] Upload front photo, verify preview
- [ ] Upload back photo, verify preview
- [ ] **OCR Testing**:
  - [ ] Verify loading message appears after both photos uploaded
  - [ ] Wait 30 seconds for OCR processing
  - [ ] Verify form fields auto-filled with extracted data
  - [ ] Check fields with high confidence are locked (readonly, gray background)
  - [ ] Check fields with low confidence remain editable
  - [ ] Verify success message displayed
- [ ] Add multiple family members and verify each has independent uploaders
- [ ] Remove family member and verify uploaders cleaned up
- [ ] Submit form and verify all family member data saved with UID URLs and OCR results

## Troubleshooting

### OCR Not Triggering
- **Check**: Both front and back photos uploaded?
- **Check**: Network tab - is POST request sent to OCR endpoint?
- **Check**: Console for JavaScript errors
- **Fix**: Verify OCR endpoint is accessible

### Photos Not Uploading
- **Check**: TUS endpoint accessible? (`https://tus.dca.arungas.com/files/`)
- **Check**: File size within limits?
- **Check**: File type is image?
- **Check**: Console for Uppy errors

### OCR Data Not Pre-filling
- **Check**: OCR response format matches expected JSON structure
- **Check**: Field name patterns match: `family_member_{memberId}_name`, etc.
- **Check**: Console for prefill errors

### Form Submission Issues
- **Check**: `collectFamilyMemberData()` returns valid data
- **Check**: All required photos uploaded
- **Check**: CSRF token included in POST request
- **Check**: Backend view handles JSON correctly

## API Endpoints

### OCR Processing
- **URL**: `/app_utilities/application-utilities/get_details_for_aadhar/`
- **Method**: POST
- **Content-Type**: application/json
- **Body**:
  ```json
  {
    "uid_front_url": "https://tus.dca.arungas.com/files/abc123",
    "uid_back_url": "https://tus.dca.arungas.com/files/def456"
  }
  ```
- **Response**:
  ```json
  {
    "name": {"value": "John Doe", "prob": 0.95},
    "dob": {"value": "01/01/1990", "prob": 0.85},
    "gender": {"value": "MALE", "prob": 0.90},
    "aadhaar": {"value": "123456789012", "prob": 0.95},
    "address": {"value": "...", "prob": 0.70},
    "pincode": "110001"
  }
  ```

### Form Submission
- **URL**: `/ujjwala_v3/apply/`
- **Method**: POST
- **Content-Type**: application/json
- **Body**: See Step 5 for structure

## Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

Uppy requires modern browser features. IE11 is not supported.

## Dependencies

### Required Libraries
- **jQuery 3.6+** - DOM manipulation and AJAX
- **Bootstrap 4.6+** - UI components
- **Uppy 2.13+** - File uploads
  - Uppy Core
  - Uppy Dashboard
  - Uppy ImageEditor
  - Uppy Compressor
  - Uppy Tus

### CDN Links (Already in template)
```html
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://releases.transloadit.com/uppy/v2.13.1/uppy.min.js"></script>
<link rel="stylesheet" href="https://releases.transloadit.com/uppy/v2.13.1/uppy.min.css">
```

## Performance Considerations

1. **Image Compression**: All images are compressed before upload to reduce bandwidth
2. **Lazy Loading**: Uppy dashboards are initialized on demand
3. **OCR Async**: OCR processing is asynchronous and non-blocking
4. **Memory Management**: Uppy instances are properly closed when family members are removed

## Security Considerations

1. **File Type Validation**: Only images allowed
2. **File Size Limits**: Enforced on client and should be enforced on server
3. **CSRF Protection**: Ensure CSRF token in all AJAX requests
4. **URL Sanitization**: Validate TUS URLs before storing
5. **OCR Data Validation**: Always validate OCR-extracted data on server

## Future Enhancements

1. **Real-time OCR Progress**: Show progress bar during OCR processing
2. **Manual OCR Retry**: Button to retry OCR if it fails
3. **Photo Quality Check**: Warn if photo quality is too low
4. **Batch OCR**: Process multiple family members simultaneously
5. **Offline Support**: Cache form data for offline editing

## Support

For issues or questions:
- Check console for JavaScript errors
- Review network tab for API call issues
- Verify all files are loaded correctly
- Check Django logs for backend errors

---

**Last Updated**: 2025-11-18
**Version**: 1.0
