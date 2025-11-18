/**
 * Family Member Manager for Ujjwala V3
 * Handles adding/removing family members with UID photo upload capability
 */

let familyMemberCounter = 0;

/**
 * Add a new family member with UID photo uploaders
 */
function addFamilyMemberWithUID() {
    familyMemberCounter++;
    const memberId = familyMemberCounter;

    // Load the family member HTML template
    const memberHtml = `
        <div class="card family-member-item" id="familyMember_${memberId}" style="margin-bottom: 20px; border: 2px solid #4299e1;">
            <div class="card-header" style="background: #2d3748; color: white;">
                <div class="d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">
                        <i class="fas fa-user"></i> Family Member ${memberId}
                        <span class="member-relation-label" id="relationLabel_${memberId}"></span>
                    </h6>
                    <button type="button" class="btn btn-sm btn-danger" onclick="removeFamilyMemberWithUID(${memberId})">
                        <i class="fas fa-trash"></i> Remove
                    </button>
                </div>
            </div>
            <div class="card-body">
                <!-- Step 1: Relation to Applicant - MOST IMPORTANT -->
                <div class="alert alert-primary">
                    <i class="fas fa-users"></i> <strong>Step 1: Select Relation to Applicant</strong><br>
                    First, select the relationship of this family member to the applicant. Note: At least one SELF member must be added (representing the applicant).
                    <br><small>पहले आवेदक से इस परिवार के सदस्य का संबंध चुनें। नोट: कम से कम एक SELF सदस्य जोड़ा जाना चाहिए (आवेदक का प्रतिनिधित्व करता है)।</small>
                </div>

                <div class="row">
                    <div class="col-md-12 form-group">
                        <label class="required-field">Relation to Applicant (संबंध)</label>
                        <select name="family_member_${memberId}_relation" id="familyMember_${memberId}_relation"
                                class="form-control" required onchange="updateRelationLabel(${memberId})">
                            <option value="">-- Select Relation --</option>
                            <option value="SELF">Self (स्वयं) - Applicant</option>
                            <option value="HUSBAND">Husband (पति)</option>
                            <option value="FATHER">Father (पिता)</option>
                            <option value="MOTHER">Mother (माता)</option>
                            <option value="SON">Son (पुत्र)</option>
                            <option value="DAUGHTER">Daughter (पुत्री)</option>
                            <option value="BROTHER">Brother (भाई)</option>
                            <option value="SISTER">Sister (बहन)</option>
                            <option value="FATHER_IN_LAW">Father-in-law (ससुर)</option>
                            <option value="MOTHER_IN_LAW">Mother-in-law (सास)</option>
                            <option value="DAUGHTER_IN_LAW">Daughter-in-law (बहू)</option>
                            <option value="SON_IN_LAW">Son-in-law (दामाद)</option>
                            <option value="GRANDFATHER">Grandfather (दादा/नाना)</option>
                            <option value="GRANDMOTHER">Grandmother (दादी/नानी)</option>
                            <option value="GRANDSON">Grandson (पोता/नाती)</option>
                            <option value="GRANDDAUGHTER">Granddaughter (पोती/नातिन)</option>
                            <option value="UNCLE">Uncle (चाचा/मामा)</option>
                            <option value="AUNT">Aunt (चाची/मामी)</option>
                            <option value="OTHER">Other (अन्य)</option>
                        </select>
                    </div>
                </div>

                <!-- Step 2: Aadhaar Photo Upload (Hidden for SELF member) -->
                <div id="aadhaarUploadSection_${memberId}">
                    <div class="alert alert-secondary">
                        <i class="fas fa-camera"></i> <strong>Step 2: Upload Aadhaar/UID Photos</strong><br>
                        Upload both front and back photos of the Aadhaar card. The system will automatically extract and fill the details using OCR.
                        <br><small>आधार कार्ड के आगे और पीछे की फोटो अपलोड करें। सिस्टम OCR का उपयोग करके विवरण स्वचालित रूप से भर देगा।</small>
                    </div>

                    <div class="row">
                        <div class="col-md-6">
                            <div class="form-group">
                                <label class="required-field">Aadhaar Front Photo (आधार कार्ड आगे की तरफ)</label>
                                <div id="uidFrontUploader_${memberId}"></div>
                                <input type="hidden" name="family_member_${memberId}_uid_front_url" id="uidFrontUrl_${memberId}">
                                <div id="uidFrontPreview_${memberId}" class="mt-2"></div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="form-group">
                                <label class="required-field">Aadhaar Back Photo (आधार कार्ड पीछे की तरफ)</label>
                                <div id="uidBackUploader_${memberId}"></div>
                                <input type="hidden" name="family_member_${memberId}_uid_back_url" id="uidBackUrl_${memberId}">
                                <div id="uidBackPreview_${memberId}" class="mt-2"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- OCR Status -->
                <div id="ocrStatus_${memberId}" class="mb-3"></div>

                <!-- Step 3: Profile Photo for SELF member (hidden by default, shown only for SELF) -->
                <div id="profilePhotoSection_${memberId}" style="display:none;">
                    <div class="alert alert-info">
                        <i class="fas fa-camera"></i> <strong>Profile Photo / Selfie</strong><br>
                        Since this is the applicant (SELF), please upload a profile photo or selfie for identity verification.
                        <br><small>चूंकि यह आवेदक (SELF) है, कृपया पहचान सत्यापन के लिए एक प्रोफ़ाइल फ़ोटो या सेल्फी अपलोड करें।</small>
                    </div>
                    <div class="row">
                        <div class="col-md-12">
                            <div class="form-group">
                                <label class="required-field">Profile Photo / Selfie (प्रार्थी की फोटो)</label>
                                <div id="profilePhotoUploader_${memberId}"></div>
                                <input type="hidden" name="profile_photo_url" id="profilePhotoUrl_${memberId}">
                                <div id="profilePhotoPreview_${memberId}" class="mt-2"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Step 4: Member Details (Auto-filled by OCR or Manual Entry) -->
                <div class="alert alert-secondary">
                    <i class="fas fa-edit"></i> <strong>Step 3: Verify/Edit Member Details</strong><br>
                    After uploading photos, details will be auto-filled. Please verify and edit if needed, or fill manually if OCR fails.
                    <br><small>फोटो अपलोड करने के बाद, विवरण स्वचालित रूप से भर जाएंगे। कृपया सत्यापित करें और आवश्यकता हो तो संपादित करें।</small>
                </div>

                <!-- Basic Details Row -->
                <div class="row">
                    <div class="col-md-6 form-group">
                        <label class="required-field">Full Name (पूरा नाम)</label>
                        <input type="text" name="family_member_${memberId}_name" id="familyMember_${memberId}_name"
                               class="form-control" placeholder="As per Aadhaar" required>
                    </div>
                    <div class="col-md-3 form-group">
                        <label class="required-field">Gender (लिंग)</label>
                        <select name="family_member_${memberId}_gender" id="familyMember_${memberId}_gender"
                                class="form-control" required>
                            <option value="">-- Select --</option>
                            <option value="M">Male (पुरुष)</option>
                            <option value="F">Female (महिला)</option>
                            <option value="O">Other (अन्य)</option>
                        </select>
                    </div>
                    <div class="col-md-3 form-group">
                        <label class="required-field">Date of Birth (जन्म तिथि)</label>
                        <input type="date" name="family_member_${memberId}_dob" id="familyMember_${memberId}_dob"
                               class="form-control" required>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-12 form-group">
                        <label class="required-field">Aadhaar Number (आधार संख्या)</label>
                        <input type="text" name="family_member_${memberId}_aadhaar" id="familyMember_${memberId}_aadhaar"
                               class="form-control" placeholder="12-digit Aadhaar"
                               pattern="[0-9]{12}" maxlength="12" required>
                    </div>
                </div>

                <!-- Hidden fields for OCR data -->
                <input type="hidden" id="ocrResult_${memberId}" name="family_member_${memberId}_ocr_result">
            </div>
        </div>
    `;

    // Append to container
    $('#familyMembersContainer').append(memberHtml);

    // Initialize UID uploaders for this member
    window.photoUploadManager.initFamilyMemberUIDUploaders(memberId);

    // Scroll to the new member
    $(`#familyMember_${memberId}`)[0].scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Remove family member with cleanup
 */
function removeFamilyMemberWithUID(memberId) {
    if (confirm('Are you sure you want to remove this family member?')) {
        window.photoUploadManager.removeFamilyMember(memberId);
    }
}

/**
 * Update relation label in card header
 */
function updateRelationLabel(memberId) {
    const relation = $(`[name="family_member_${memberId}_relation"] option:selected`).text();
    $(`#relationLabel_${memberId}`).text(`(${relation})`);

    // Show/hide profile photo section and highlight SELF member
    if ($(`[name="family_member_${memberId}_relation"]`).val() === 'SELF') {
        $(`#familyMember_${memberId}`).css('border-color', '#dc3545');
        $(`#familyMember_${memberId} .card-header`).css('background', '#dc3545');

        // Show profile photo section for SELF member
        $(`#profilePhotoSection_${memberId}`).show();

        // Hide Aadhaar upload section for SELF (already uploaded in Step 1)
        $(`#aadhaarUploadSection_${memberId}`).hide();

        // Show note that Aadhaar is already uploaded
        $(`#ocrStatus_${memberId}`).html(`
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i> <strong>Note:</strong> Your Aadhaar has already been uploaded and verified in Step 1.
                <br><small>आपका आधार पहले ही चरण 1 में अपलोड और सत्यापित हो चुका है।</small>
            </div>
        `);

        // Initialize profile photo uploader if not already initialized
        setTimeout(function() {
            if (window.photoUploadManager && typeof window.photoUploadManager.initProfilePhotoUploader === 'function') {
                try {
                    console.log('Initializing profile photo uploader for member:', memberId);
                    window.photoUploadManager.initProfilePhotoUploader(memberId);
                } catch (error) {
                    console.error('Error initializing profile photo uploader:', error);
                }
            } else {
                console.warn('PhotoUploadManager not available or initProfilePhotoUploader not a function');
            }
        }, 200); // Wait for DOM to be fully rendered
    } else {
        $(`#familyMember_${memberId}`).css('border-color', '#4299e1');
        $(`#familyMember_${memberId} .card-header`).css('background', '#2d3748');

        // Hide profile photo section for non-SELF members
        $(`#profilePhotoSection_${memberId}`).hide();

        // Show Aadhaar upload for other members
        $(`#aadhaarUploadSection_${memberId}`).show();
        $(`#ocrStatus_${memberId}`).html('');
    }
}

/**
 * Collect all family member data for submission
 */
function collectFamilyMemberData() {
    const familyMembers = [];

    $('.family-member-item').each(function() {
        const memberId = $(this).attr('id').replace('familyMember_', '');
        const memberData = window.photoUploadManager.getFamilyMemberData(memberId);

        if (memberData.name && memberData.relation) {
            familyMembers.push(memberData);
        }
    });

    return familyMembers;
}

/**
 * Validate that at least one SELF member exists
 */
function validateFamilyMembers() {
    const hasSelf = $('[name^="family_member_"][name$="_relation"]').filter(function() {
        return $(this).val() === 'SELF';
    }).length > 0;

    if (!hasSelf) {
        alert('Error: You must add yourself (SELF) as a family member.');
        return false;
    }

    // Validate UID photos uploaded for all members
    let allHavePhotos = true;
    $('.family-member-item').each(function() {
        const memberId = $(this).attr('id').replace('familyMember_', '');
        const frontUrl = $(`#uidFrontUrl_${memberId}`).val();
        const backUrl = $(`#uidBackUrl_${memberId}`).val();

        if (!frontUrl || !backUrl) {
            const name = $(`[name="family_member_${memberId}_name"]`).val() || 'Unnamed member';
            alert(`Error: Please upload both Aadhaar front and back photos for ${name}`);
            allHavePhotos = false;
            return false;
        }
    });

    return hasSelf && allHavePhotos;
}

// Initialize when document is ready
$(document).ready(function() {
    // Bind the add family member button
    $('#addFamilyMember').click(function() {
        addFamilyMemberWithUID();
    });

    // Add first SELF member automatically on page load if container is empty
    if ($('#familyMembersContainer').children().length === 0) {
        // Could add SELF member here or wait for OCR
        console.log('Family members container is empty. Add members manually or via OCR.');
    }
});
