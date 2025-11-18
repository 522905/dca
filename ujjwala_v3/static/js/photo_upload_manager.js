/**
 * Ujjwala V3 Form - Photo Upload and OCR Processing
 * Handles profile photo, bank passbook, and family member UID photos with OCR
 */

class PhotoUploadManager {
    constructor() {
        this.tusEndpoint = 'https://tus.dca.arungas.com/files/';
        this.ocrEndpoint = '/app_utilities/application-utilities/get_details_for_aadhar/';
        this.uploaders = {};
        this.familyMemberData = new Map();
    }

    /**
     * Initialize profile photo uploader
     */
    initProfilePhotoUploader() {
        // Check if already initialized
        if (this.uploaders.profile) {
            console.log('Profile photo uploader already initialized');
            return;
        }

        const profileUppy = new Uppy.Core({
            autoProceed: true, // Auto-upload after file selection
            maxFileSize: 10000000, // 10 MB
            maxNumberOfFiles: 1,
            allowedFileTypes: ['image/*'],
            restrictions: {
                maxFileSize: 10000000,
                maxNumberOfFiles: 1,
                minNumberOfFiles: null,
                allowedFileTypes: ['image/*']
            }
        })
        .use(Uppy.Dashboard, {
            inline: true,
            target: '#profilePhotoUploader',
            height: 250,
            hideUploadButton: true, // Hide manual upload button since auto-upload is enabled
            showRemoveButtonAfterComplete: false,
            note: 'Images only, up to 10 MB'
        })
        .use(Uppy.ImageEditor, {
            target: Uppy.Dashboard
        })
        .use(Uppy.Compressor, {
            quality: 0.9,
            maxWidth: 1024,
            maxHeight: 1024
        })
        .use(Uppy.Tus, {
            endpoint: this.tusEndpoint
        });

        profileUppy.on('upload-success', (file, response) => {
            const photoUrl = response.uploadURL;
            $('#profilePhotoUrl').val(photoUrl);

            // Hide uploader and show preview with hover actions
            $('#profilePhotoUploader').hide();
            $('#profilePhotoPreview').html(`
                <div class="photo-preview-container" style="position: relative; display: inline-block;">
                    <img src="${photoUrl}" alt="Profile Photo"
                         style="max-width: 200px; border-radius: 8px; border: 2px solid #28a745; cursor: pointer;">
                    <div class="photo-hover-actions" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
                         display: none; background: rgba(0,0,0,0.7); padding: 10px; border-radius: 8px;">
                        <button type="button" class="btn btn-sm btn-light mx-1" onclick="viewImage('${photoUrl}', 'Profile Photo')">
                            <i class="fas fa-search-plus"></i> Zoom
                        </button>
                        <button type="button" class="btn btn-sm btn-warning mx-1" onclick="window.photoUploadManager.changeProfilePhoto()">
                            <i class="fas fa-edit"></i> Change
                        </button>
                    </div>
                </div>
                <p class="text-success mt-2"><i class="fas fa-check-circle"></i> Profile photo uploaded successfully!</p>
            `).show();

            // Add hover effect
            $('.photo-preview-container').hover(
                function() { $(this).find('.photo-hover-actions').fadeIn(200); },
                function() { $(this).find('.photo-hover-actions').fadeOut(200); }
            );

            console.log('Profile photo uploaded:', photoUrl);
        });

        profileUppy.on('upload-error', (file, error, response) => {
            console.error('Profile photo upload error:', error);
            alert('Failed to upload profile photo. Please try again.');
        });

        this.uploaders.profile = profileUppy;
    }

    /**
     * Change profile photo - show uploader again
     */
    changeProfilePhoto() {
        $('#profilePhotoUploader').show();
        $('#profilePhotoPreview').hide();
        // Reset uploader
        if (this.uploaders.profile) {
            this.uploaders.profile.reset();
        }
    }

    /**
     * Initialize bank passbook photo uploader
     */
    initBankPassbookUploader() {
        // Check if already initialized
        if (this.uploaders.bankPassbook) {
            console.log('Bank passbook uploader already initialized');
            return;
        }

        const passbookUppy = new Uppy.Core({
            autoProceed: true, // Auto-upload after file selection
            maxFileSize: 10000000, // 10 MB
            maxNumberOfFiles: 1,
            allowedFileTypes: ['image/*'],
            restrictions: {
                maxFileSize: 10000000,
                maxNumberOfFiles: 1,
                minNumberOfFiles: null,
                allowedFileTypes: ['image/*']
            }
        })
        .use(Uppy.Dashboard, {
            inline: true,
            target: '#bankPassbookUploader',
            height: 250,
            hideUploadButton: true, // Hide manual upload button since auto-upload is enabled
            showRemoveButtonAfterComplete: false,
            note: 'Images only, up to 10 MB'
        })
        .use(Uppy.ImageEditor, {
            target: Uppy.Dashboard
        })
        .use(Uppy.Compressor, {
            quality: 0.9,
            maxWidth: 2048,
            maxHeight: 2048
        })
        .use(Uppy.Tus, {
            endpoint: this.tusEndpoint
        });

        passbookUppy.on('upload-success', (file, response) => {
            const photoUrl = response.uploadURL;
            $('#bankPassbookUrl').val(photoUrl);

            // Hide uploader and show preview with hover actions
            $('#bankPassbookUploader').hide();
            $('#bankPassbookPreview').html(`
                <div class="photo-preview-container" style="position: relative; display: inline-block;">
                    <img src="${photoUrl}" alt="Bank Passbook"
                         style="max-width: 300px; border-radius: 8px; border: 2px solid #28a745; cursor: pointer;">
                    <div class="photo-hover-actions" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
                         display: none; background: rgba(0,0,0,0.7); padding: 10px; border-radius: 8px;">
                        <button type="button" class="btn btn-sm btn-light mx-1" onclick="viewImage('${photoUrl}', 'Bank Passbook')">
                            <i class="fas fa-search-plus"></i> Zoom
                        </button>
                        <button type="button" class="btn btn-sm btn-warning mx-1" onclick="window.photoUploadManager.changeBankPassbookPhoto()">
                            <i class="fas fa-edit"></i> Change
                        </button>
                    </div>
                </div>
                <p class="text-success mt-2"><i class="fas fa-check-circle"></i> Bank passbook uploaded successfully!</p>
            `).show();

            // Add hover effect
            $('.photo-preview-container').hover(
                function() { $(this).find('.photo-hover-actions').fadeIn(200); },
                function() { $(this).find('.photo-hover-actions').fadeOut(200); }
            );

            console.log('Bank passbook uploaded:', photoUrl);
        });

        passbookUppy.on('upload-error', (file, error, response) => {
            console.error('Bank passbook upload error:', error);
            alert('Failed to upload bank passbook. Please try again.');
        });

        this.uploaders.bankPassbook = passbookUppy;
    }

    /**
     * Change bank passbook photo - show uploader again
     */
    changeBankPassbookPhoto() {
        $('#bankPassbookUploader').show();
        $('#bankPassbookPreview').hide();
        // Reset uploader
        if (this.uploaders.bankPassbook) {
            this.uploaders.bankPassbook.reset();
        }
    }

    /**
     * Initialize UID photo uploaders for a family member
     */
    initFamilyMemberUIDUploaders(memberId) {
        // UID Front uploader
        const frontUppy = new Uppy.Core({
            id: `uidFront_${memberId}`,
            autoProceed: true, // Auto-upload after file selection
            maxFileSize: 50000000,
            maxNumberOfFiles: 1,
            allowedFileTypes: ['image/*'],
        })
        .use(Uppy.Dashboard, {
            inline: true,
            target: `#uidFrontUploader_${memberId}`,
            height: 200,
            hideUploadButton: true,
            showRemoveButtonAfterComplete: false,
            note: 'Aadhaar Front - Images only, up to 50 MB'
        })
        .use(Uppy.ImageEditor, {
            target: Uppy.Dashboard
        })
        .use(Uppy.Compressor, {
            quality: 0.92,
            maxWidth: 1520
        })
        .use(Uppy.Tus, {
            endpoint: this.tusEndpoint
        });

        // UID Back uploader
        const backUppy = new Uppy.Core({
            id: `uidBack_${memberId}`,
            autoProceed: true, // Auto-upload after file selection
            maxFileSize: 50000000,
            maxNumberOfFiles: 1,
            allowedFileTypes: ['image/*'],
        })
        .use(Uppy.Dashboard, {
            inline: true,
            target: `#uidBackUploader_${memberId}`,
            height: 200,
            hideUploadButton: true,
            showRemoveButtonAfterComplete: false,
            note: 'Aadhaar Back - Images only, up to 50 MB'
        })
        .use(Uppy.ImageEditor, {
            target: Uppy.Dashboard
        })
        .use(Uppy.Compressor, {
            quality: 0.92,
            maxWidth: 1520
        })
        .use(Uppy.Tus, {
            endpoint: this.tusEndpoint
        });

        // Initialize member data storage
        if (!this.familyMemberData.has(memberId)) {
            this.familyMemberData.set(memberId, {
                uid_front_url: null,
                uid_back_url: null,
                uid_original_front_url: null,
                uid_original_back_url: null,
                ocr_result: null
            });
        }

        const memberData = this.familyMemberData.get(memberId);

        frontUppy.on('upload-success', (file, response) => {
            memberData.uid_front_url = response.uploadURL;
            memberData.uid_original_front_url = response.uploadURL;
            $(`#uidFrontUrl_${memberId}`).val(response.uploadURL);

            // Hide uploader and show preview with hover actions
            $(`#uidFrontUploader_${memberId}`).hide();
            $(`#uidFrontPreview_${memberId}`).html(`
                <div class="photo-preview-container" style="position: relative; display: inline-block;">
                    <img src="${response.uploadURL}" alt="UID Front"
                         style="max-width: 200px; border: 2px solid #28a745; border-radius: 5px; cursor: pointer;">
                    <div class="photo-hover-actions" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
                         display: none; background: rgba(0,0,0,0.7); padding: 10px; border-radius: 8px;">
                        <button type="button" class="btn btn-sm btn-light mx-1" onclick="viewImage('${response.uploadURL}', 'Aadhaar Front')">
                            <i class="fas fa-search-plus"></i> Zoom
                        </button>
                        <button type="button" class="btn btn-sm btn-warning mx-1" onclick="window.photoUploadManager.changeUIDPhoto(${memberId}, 'front')">
                            <i class="fas fa-edit"></i> Change
                        </button>
                    </div>
                </div>
            `).show();

            // Add hover effect
            $(`#uidFrontPreview_${memberId} .photo-preview-container`).hover(
                function() { $(this).find('.photo-hover-actions').fadeIn(200); },
                function() { $(this).find('.photo-hover-actions').fadeOut(200); }
            );

            this.checkAndTriggerOCR(memberId);
        });

        backUppy.on('upload-success', (file, response) => {
            memberData.uid_back_url = response.uploadURL;
            memberData.uid_original_back_url = response.uploadURL;
            $(`#uidBackUrl_${memberId}`).val(response.uploadURL);

            // Hide uploader and show preview with hover actions
            $(`#uidBackUploader_${memberId}`).hide();
            $(`#uidBackPreview_${memberId}`).html(`
                <div class="photo-preview-container" style="position: relative; display: inline-block;">
                    <img src="${response.uploadURL}" alt="UID Back"
                         style="max-width: 200px; border: 2px solid #28a745; border-radius: 5px; cursor: pointer;">
                    <div class="photo-hover-actions" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
                         display: none; background: rgba(0,0,0,0.7); padding: 10px; border-radius: 8px;">
                        <button type="button" class="btn btn-sm btn-light mx-1" onclick="viewImage('${response.uploadURL}', 'Aadhaar Back')">
                            <i class="fas fa-search-plus"></i> Zoom
                        </button>
                        <button type="button" class="btn btn-sm btn-warning mx-1" onclick="window.photoUploadManager.changeUIDPhoto(${memberId}, 'back')">
                            <i class="fas fa-edit"></i> Change
                        </button>
                    </div>
                </div>
            `).show();

            // Add hover effect
            $(`#uidBackPreview_${memberId} .photo-preview-container`).hover(
                function() { $(this).find('.photo-hover-actions').fadeIn(200); },
                function() { $(this).find('.photo-hover-actions').fadeOut(200); }
            );

            this.checkAndTriggerOCR(memberId);
        });

        this.uploaders[`uidFront_${memberId}`] = frontUppy;
        this.uploaders[`uidBack_${memberId}`] = backUppy;
    }

    /**
     * Change UID photo - show uploader again
     */
    changeUIDPhoto(memberId, side) {
        if (side === 'front') {
            $(`#uidFrontUploader_${memberId}`).show();
            $(`#uidFrontPreview_${memberId}`).hide();
            if (this.uploaders[`uidFront_${memberId}`]) {
                this.uploaders[`uidFront_${memberId}`].reset();
            }
        } else {
            $(`#uidBackUploader_${memberId}`).show();
            $(`#uidBackPreview_${memberId}`).hide();
            if (this.uploaders[`uidBack_${memberId}`]) {
                this.uploaders[`uidBack_${memberId}`].reset();
            }
        }
    }

    /**
     * Check if both UID photos are uploaded and trigger OCR
     */
    checkAndTriggerOCR(memberId) {
        const memberData = this.familyMemberData.get(memberId);

        if (memberData.uid_front_url && memberData.uid_back_url && !memberData.ocr_result) {
            this.processOCR(memberId);
        }
    }

    /**
     * Process OCR for family member UID
     */
    async processOCR(memberId) {
        const memberData = this.familyMemberData.get(memberId);

        // Show loading
        $(`#ocrStatus_${memberId}`).html(`
            <div class="alert alert-info">
                <i class="fas fa-spinner fa-spin"></i> Processing OCR... This may take 30 seconds. Please wait.
                <br><small>OCR 30 सेकंड लेता है, कृपया प्रतीक्षा करें</small>
            </div>
        `);

        try {
            const response = await $.ajax({
                url: this.ocrEndpoint,
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    uid_front_url: memberData.uid_front_url,
                    uid_back_url: memberData.uid_back_url
                })
            });

            memberData.ocr_result = response;
            this.prefillFromOCR(memberId, response);

            $(`#ocrStatus_${memberId}`).html(`
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i> OCR completed successfully! Data has been pre-filled.
                </div>
            `);

            // Auto-hide success message after 5 seconds
            setTimeout(() => {
                $(`#ocrStatus_${memberId}`).fadeOut();
            }, 5000);

        } catch (error) {
            console.error('OCR Error:', error);
            $(`#ocrStatus_${memberId}`).html(`
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i> OCR failed or data quality is low. Please fill the details manually.
                </div>
            `);
        }
    }

    /**
     * Prefill form fields from OCR data
     */
    prefillFromOCR(memberId, ocrData) {
        console.log('OCR Data for member', memberId, ':', ocrData);

        // Extract data with confidence checking
        const getName = (data) => data.name?.value || '';
        const getDOB = (data) => {
            if (!data.dob?.value) return '';
            // Convert DD/MM/YYYY to YYYY-MM-DD
            const parts = data.dob.value.split('/');
            if (parts.length === 3) {
                return `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
            }
            return '';
        };
        const getGender = (data) => {
            const gender = data.gender?.value?.toUpperCase();
            if (gender === 'MALE' || gender === 'M') return 'M';
            if (gender === 'FEMALE' || gender === 'F') return 'F';
            return 'O';
        };
        const getAadhaar = (data) => data.aadhaar?.value || data.uid?.value || '';

        // Prefill fields
        const name = getName(ocrData);
        const dob = getDOB(ocrData);
        const gender = getGender(ocrData);
        const aadhaar = getAadhaar(ocrData);

        if (name) {
            $(`[name="family_member_${memberId}_name"]`).val(name);
            // Lock if high confidence
            if (ocrData.name?.prob >= 0.8) {
                $(`[name="family_member_${memberId}_name"]`).attr('readonly', true).css('background-color', '#e9ecef');
            }
        }

        if (dob) {
            $(`[name="family_member_${memberId}_dob"]`).val(dob);
            if (ocrData.dob?.prob >= 0.8) {
                $(`[name="family_member_${memberId}_dob"]`).attr('readonly', true).css('background-color', '#e9ecef');
            }
        }

        if (gender) {
            $(`[name="family_member_${memberId}_gender"]`).val(gender);
            if (ocrData.gender?.prob >= 0.8) {
                $(`[name="family_member_${memberId}_gender"]`).attr('readonly', true).css('background-color', '#e9ecef');
            }
        }

        if (aadhaar) {
            $(`[name="family_member_${memberId}_aadhaar"]`).val(aadhaar);
            if (ocrData.aadhaar?.prob >= 0.8 || ocrData.uid?.prob >= 0.8) {
                $(`[name="family_member_${memberId}_aadhaar"]`).attr('readonly', true).css('background-color', '#e9ecef');
            }
        }

        // Store OCR result
        $(`#ocrResult_${memberId}`).val(JSON.stringify(ocrData));
    }

    /**
     * Get family member data for submission
     */
    getFamilyMemberData(memberId) {
        const memberData = this.familyMemberData.get(memberId) || {};
        return {
            name: $(`[name="family_member_${memberId}_name"]`).val(),
            relation: $(`[name="family_member_${memberId}_relation"]`).val(),
            gender: $(`[name="family_member_${memberId}_gender"]`).val(),
            dob: $(`[name="family_member_${memberId}_dob"]`).val(),
            aadhaar_number: $(`[name="family_member_${memberId}_aadhaar"]`).val(),
            uid_front_link: memberData.uid_front_url,
            uid_back_link: memberData.uid_back_url,
            uid_original_front_link: memberData.uid_original_front_url,
            uid_original_back_link: memberData.uid_original_back_url,
            uid_check_result: memberData.ocr_result,
            is_valid_uid: !!memberData.ocr_result,
            validated: !!memberData.ocr_result
        };
    }

    /**
     * Remove family member and cleanup uploaders
     */
    removeFamilyMember(memberId) {
        // Cleanup uploaders
        if (this.uploaders[`uidFront_${memberId}`]) {
            this.uploaders[`uidFront_${memberId}`].close();
            delete this.uploaders[`uidFront_${memberId}`];
        }
        if (this.uploaders[`uidBack_${memberId}`]) {
            this.uploaders[`uidBack_${memberId}`].close();
            delete this.uploaders[`uidBack_${memberId}`];
        }

        // Remove data
        this.familyMemberData.delete(memberId);

        // Remove DOM element
        $(`#familyMember_${memberId}`).remove();
    }
}

// Global instance
window.photoUploadManager = new PhotoUploadManager();

// Initialize on document ready
$(document).ready(function() {
    console.log('Initializing Photo Upload Manager...');

    // Initialize profile photo uploader if element exists
    if ($('#profilePhotoUploader').length) {
        window.photoUploadManager.initProfilePhotoUploader();
    }

    // Initialize bank passbook uploader if element exists
    if ($('#bankPassbookUploader').length) {
        window.photoUploadManager.initBankPassbookUploader();
    }
});
