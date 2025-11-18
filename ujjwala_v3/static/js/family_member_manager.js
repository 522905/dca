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
        <div class="card family-member-item" id="familyMember_${memberId}" style="margin-bottom: 20px; border: 2px solid #667eea;">
            <div class="card-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
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
                <!-- Basic Details Row -->
                <div class="row">
                    <div class="col-md-6 form-group">
                        <label class="required-field">Full Name (पूरा नाम)</label>
                        <input type="text" name="family_member_${memberId}_name"
                               class="form-control" placeholder="As per Aadhaar" required>
                    </div>
                    <div class="col-md-6 form-group">
                        <label class="required-field">Relation to Applicant (संबंध)</label>
                        <select name="family_member_${memberId}_relation" class="form-control" required
                                onchange="updateRelationLabel(${memberId})">
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

                <div class="row">
                    <div class="col-md-4 form-group">
                        <label class="required-field">Gender (लिंग)</label>
                        <select name="family_member_${memberId}_gender" class="form-control" required>
                            <option value="">-- Select --</option>
                            <option value="M">Male (पुरुष)</option>
                            <option value="F">Female (महिला)</option>
                            <option value="O">Other (अन्य)</option>
                        </select>
                    </div>
                    <div class="col-md-4 form-group">
                        <label class="required-field">Date of Birth (जन्म तिथि)</label>
                        <input type="date" name="family_member_${memberId}_dob" class="form-control" required>
                    </div>
                    <div class="col-md-4 form-group">
                        <label class="required-field">Aadhaar Number (आधार संख्या)</label>
                        <input type="text" name="family_member_${memberId}_aadhaar"
                               class="form-control" placeholder="12-digit Aadhaar"
                               pattern="[0-9]{12}" maxlength="12" required>
                    </div>
                </div>

                <!-- UID Photo Upload Section -->
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> <strong>Upload Aadhaar/UID Photos</strong><br>
                    Upload both front and back photos of the Aadhaar card. The system will automatically extract details using OCR.
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

                <!-- OCR Status -->
                <div id="ocrStatus_${memberId}"></div>

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

    // Highlight SELF member
    if ($(`[name="family_member_${memberId}_relation"]`).val() === 'SELF') {
        $(`#familyMember_${memberId}`).css('border-color', '#dc3545');
        $(`#familyMember_${memberId} .card-header`).css('background', 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)');
    } else {
        $(`#familyMember_${memberId}`).css('border-color', '#667eea');
        $(`#familyMember_${memberId} .card-header`).css('background', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)');
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
