
function checkContactMobileValidity() {

    var mobile = $("#uid_linked_mobile").val();

    if($("#uid_linked_mobile" ).attr("validated_value")==mobile) return;

    $("#contact_mobile_detail").html('');
    if (!mobile){
        document.getElementById("uid_linked_mobile").setCustomValidity("Invalid mobile number.");
        document.getElementById("uid_linked_mobile").reportValidity();
        // document.getElementById("uid_linked_mobile").focus();
        return;
    }

    if (!(mobile.match(/^[6789][0-9]{9}$/))){
        document.getElementById("uid_linked_mobile").setCustomValidity("Invalid mobile number.");
        document.getElementById("uid_linked_mobile").reportValidity();
        // document.getElementById("uid_linked_mobile").focus();
        return;
    }
    $("#contact_mobile_detail").show();
    $("#contact_mobile_detail").html('<img style="width:18px; margin-left:10px;" align="left">&nbsp;Checking Mobile...');

    $("#uid_linked_mobile" ).attr("validated_value", mobile);

    jQuery.ajax({
        url: '/ujjwala/ujjwala-application/check_phone/',
        type: "GET",
        data: {'contact_mobile': mobile},
        success: function (data) {
            response = data;
            if (response.status === true) {
                $("#contact_mobile_detail").show();
                $("#contact_mobile_detail").html('✔ Available for New Application').css({'color': 'green', 'font-size' : '14px'});
                document.getElementById("uid_linked_mobile").setCustomValidity("")
                document.getElementById("uid_linked_mobile").reportValidity();
                return true;
            } else {
                console.log(response);
                var datas = response.data;
                var msg = response.msg;
                var status = response.status;
                var applications = datas.applications;


                window.alert(`आपका आवेदन पहले से मौजूद है आइ डी: ${applications[0].id} और नाम ${applications[0].name} स्टेटस ` + msg);
                document.getElementById("uid_linked_mobile").setCustomValidity(`ID: ${applications[0].id} Name: ${applications[0].name}`);
                document.getElementById("uid_linked_mobile").reportValidity();

                msg = applications.map(e=>`<p>आपका आवेदन पहले से मौजूद है ${e.id} Name: ${e.name}</p>`).join('');

                $("#contact_mobile_detail").html(msg).css({'color': 'red', 'font-size' : '17px'});
            }
        },
    });
};

function checkMobileValidity() {
    var mobile = $("#contact_mobile").val();

    if($("#mobile_detail" ).attr("validated_value")==mobile) return;

    $("#mobile_detail").html('');
    if (!mobile){
        document.getElementById("contact_mobile").setCustomValidity("Invalid mobile number.");
        document.getElementById("contact_mobile").reportValidity();
        // document.getElementById("contact_mobile").focus();
        return;
    }

    if (!(mobile.match(/^[6789][0-9]{9}$/))){
        document.getElementById("contact_mobile").setCustomValidity("Invalid mobile number.");
        document.getElementById("contact_mobile").reportValidity();
        // document.getElementById("contact_mobile").focus();
        return;
    }
    $("#mobile_detail").show();
    $("#mobile_detail").html('<img style="width:18px; margin-left:10px;" align="left"> Checking Mobile...');

    $("#mobile_detail" ).attr("validated_value", mobile);

    //Disable Dedup

    $('#verifyWhatsappButton').attr('disabled', true);

    jQuery.ajax({
        url: '/ujjwala/ujjwala-application/check_phone/',
        type: "GET",
        data: {'contact_mobile': mobile},
        success: function (data) {
            response = data;
            if (response.status === true) {
                $("#mobile_detail").show();
                $("#mobile_detail").html('✔ Available for New Application').css({'color': 'green', 'font-size' : '14px'});
                document.getElementById("contact_mobile").setCustomValidity("")
                document.getElementById("contact_mobile").reportValidity();
                $('#verifyWhatsappButton').attr('disabled', false);
                return true;
            } else {
                console.log(response);
                var datas = response.data;
                var msg = response.msg;
                var status = response.status;
                var applications = datas.applications;
                window.alert(`आपका व्हाट्सएप नंबर पहले से मौजूद है ID: ${applications[0].id} and Name ${applications[0].name} `);

                document.getElementById("contact_mobile").setCustomValidity(`ID: ${applications[0].id} Name: ${applications[0].name}`);
                document.getElementById("contact_mobile").reportValidity();

                msg = applications.map(e=>`<p>आपका व्हाट्सएप नंबर पहले से मौजूद है ${e.id} Name: ${e.name}</p>`).join('');

                $("#mobile_detail").html(msg).css({'color': 'red', 'font-size' : '17px'});
            }
        },
    });
};

function init_sign_document() {
    $('#signature-pad').addClass("show-sign-block");
}

function close_sign_document() {
    $('#signature-pad').removeClass("show-sign-block");
}

function validate_pincode() {
    if(!$('#pincode')[0].reportValidity()) {
        return;
    }
    pincode = parseInt($('#pincode').val());
    if(pincode && pincode >= 141001 && pincode <= 141015) {
        return true;
    }
    alert("We don't provide service this Pin code area. हम इस पिन कोड क्षेत्र में सेवा प्रदान नहीं करते हैं");
    return false;
}

function validateAadhaarrUniquness() {
    let uid_list = $('.familyMemberLineItem .aadhar_on_blur').get().map(e=>e.value);
    let uid_length =uid_list.length
    let uid_uniq_length = uid_list.filter((item, i, ar) => ar.indexOf(item) === i).length;

    if (uid_length != uid_uniq_length) {
        alert("Duplicate UID entered for family members, please check.");
        return false;
    }

    // if ($('[id="applicant-uid_no"]').val() != $('[id="SELF-uid_no"]').val()) {
    //     alert("Applicant UID mismatch, please enter UID again");
    //     return false;
    // }
    return true;

}

function validate_terms_conditions() {
    if (!$('#term_condition_agree').is(':checked')) {
        alert("Please read the terms and then tick both checkboxes. कृपया शर्तें पढ़ लीजिए और फिर चेक बॉक्स पर टिक कीजिए |");
        return false;
    }
    return true;
}

function validate_family_terms(){
    if(!$('#family_terms_condition').is(':checked')){
        alert("Please read the terms and then tick both checkboxes. कृपया शर्तें पढ़ लीजिए और फिर दोनों चेक बॉक्स पर टिक कीजिए |");
        return false;
    }
    return true;
}

function verificationAlert() {
    var self_name = document.getElementById("SELF-name").value;
    var self_dob = document.getElementById("SELF-dob").value;
    var self_uid = document.getElementById("SELF-uid_no").value;

    var husband_name = document.getElementById("HUSBAND-name").value;
    var husband_dob = document.getElementById("HUSBAND-dob").value;
    var husband_uid = document.getElementById("HUSBAND-uid_no").value;

    // Function to add hyphens after every 4 digits
    function addHyphens(uid) {
        return uid.replace(/(\d{4})(\d{4})(\d{4})/, '$1-$2-$3');
    }

    // Add hyphens to UID numbers
    self_uid = addHyphens(self_uid);
    husband_uid = addHyphens(husband_uid);

    var result = confirm("Please check Personal details.\n" +
        "Self_name: " + self_name + "\n" +
        "Self_DOB: " + self_dob + "\n" +
        "Self_uid: " + self_uid + "\n" +

        "Husband_name: " + husband_name + "\n" +
        "Husband_DOB: " + husband_dob + "\n" +
        "Husband_uid: " + husband_uid + "\n" +
        "Do you want to edit the personal detail than click cancel and go back to form. Otherwise click OK to Submit");
        return result;

    if (result) {
        alert("Form submitted!");
        return result;
    } else {
        alert("Click Button to go back to the form.");
    }
}

async function upload_sign_and_submit() {
    if(!$('#form')[0].reportValidity()) {
        alert("Please complete all required fields");
        return;
    }

    if(!validateAadhaarrUniquness()) {
        return;
    }

    if (!validate_pincode()) {
        return;
    }

    if (!validate_terms_conditions()) {
        return;
    }

    if (!validate_family_terms()){
        return;
    }

    if (!verificationAlert()){
        return;
    }

    if (!whatsapp_verifier.is_valid()) {
        return;
    }

    family_member_service.is_valid().then(fm_service_valid => {
        debugger;
        if (!fm_service_valid) {
            return;
        }
    
        if (valid() == null) {
            return;
        }
    
        if (signaturePad.isEmpty()) {
            alert("Please provide a signature first.");
        } else {
            jQuery('#submit').html('Please wait...');
            jQuery('#submit').attr('disabled', true);
    
            var dataURL = signaturePad.toDataURL();
            var blob = dataURLToBlob(dataURL);
    
    
            let sign_uppy = new Uppy.Core({
                debug: true,
                autoProceed: true,
                restrictions: {
                    maxFileSize: 50000000,
                    maxNumberOfFiles: 1,
                    minNumberOfFiles: 1,
                    allowedFileTypes: ['image/*'],
                }
            })
            .use(Uppy.Tus, {
                endpoint: 'https://tus.dca.arungas.com/files/',
            });
    
            sign_uppy.addFile({
                name: `signature_${new Date().getTime()}_${(Math.random() + 1).toString(36).substring(7)}.png`,
                type: 'image/png',
                data: blob,
                source: 'Local', // optional, determines the source of the file, for example, Instagram.
                isRemote: false, // optional, set to true if actual file is not in the browser, but on some remote server, for example,
            });
            sign_uppy.upload().then((result) => {
                if (result.failed.length > 0) {
                    alert("Error Uploading Signature, try again");
                    console.error('Errors:')
                    result.failed.forEach((file) => {
                        console.error(file.error)
                    });
    
                    jQuery('#submit').html('Submit');
                    jQuery('#submit').attr('disabled', false);
    
                } else {
                    console.info('Successful uploads:', result.successful);
                    submit_form(result.successful[0].uploadURL)
                }
            });
    
        }
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function submit_form(signature_url) {
    event.preventDefault();
    let documentArray = valid();

    let formdata = $('form').serializeArray(
    ).reduce((accum, item) => {
        if (-1 === ['ignoreThis', 'andThat'].indexOf(item.name)) {
            if (item.value !== null) {
                accum[item.name] = item.value;
            }
        }
        return accum;
    }, {});

    formdata.address_json = {
        house_no: formdata.house_no,
        floor: formdata.floor,
        room_no: formdata.room_no,
        street_no: formdata.street_no,
        ward_no: formdata.ward_no,
        landmark: formdata.landmark,
        pincode: formdata.pincode,
        village: formdata.village,
        post_office: formdata.post_office,
        city: formdata.city
    }

    formdata.documents = documentArray;
    formdata.family_members = gatherFamilyMembersData();

    formdata.documents.push({
        type: 'CUSTOMER_SIGNATURE',
        link: signature_url
    });

    // if(formdata.uid_mobile_status == 'LINKED_WITH_SAME_MOBILE') {
    //     formdata.uid_linked_mobile = formdata.contact_mobile;
    // } else if (formdata.uid_mobile_status == 'LINKED_WITH_OTHER_MOBILE') {
    //     formdata.uid_linked_mobile = '';
    // }
    let self = formdata.family_members.filter(
        (e) => {return e.relation == 'SELF'}
    )[0]
    formdata.name = self.name;

    console.log(formdata);

    jQuery('#submit').html('Please wait...');
    jQuery('#submit').attr('disabled', true);

    var formData = new FormData($('#form')[0]);

    jQuery.ajax({
        url: '/ujjwala/ujjwala-application/wf/',
        type: 'POST',
        data: JSON.stringify(formdata),
        contentType: "application/json; charset=utf-8",
        dataType: 'JSON',
        headers: {'X-CSRFToken': getCookie('csrftoken')},

        processData: false,
        success: function (result) {

            $('#form').hide();
            console.log(result);
            jQuery('#form')['0'].reset();
            jQuery('#submit').val('Submit');
            jQuery('#submit').attr('disabled', false);
            swal({
                html: true,
                title: "successful",
                text: "Thank You ",
                icon: "success",
            })

            $("#message").html('<div class="alert alert-success" style="color:red; text-align:center; margin-top:250px;"><strong>SUCCESS!</strong> your application has been submitted</div>');

            $("#cus_id").append(result);
            $("#message").append(result.id).css({"text-align": "center"}).append(" <b> is you application Id</b>.");

            $('#application_receipt').show();
        },
        error: function (error) {
            console.log(error);
            alert('Please Check input data and try.');
            alert(JSON.stringify(error));
            jQuery('#submit').html('Submit');
            jQuery('#submit').attr('disabled', false);
        }

    });
}

function valid() {
    let files = [
        validateUppy(customerpictureuppy, 'CUSTOMER_PHOTO', 'Customer Picture or Selfie (ग्राहक की फोटो)*', true),
        validateUppy(bankdetailuppy, 'BANK_DETAIL', 'Bank Detail (पास बुक का विवरण)', true)
    ];

    if (!files.reduce((aggr, current) => {
        return current.valid && aggr
    }, true)) {
        let error = files.reduce((aggr, current) => {
            if (current.msg) {
                return aggr + '\n' + current.msg
            } else {
                return aggr
            }
        }, '');
        window.alert(error);
        return null;
    }
    let documentArray = files.filter(e => e.url).map(e => {
        return {type: e.key, link: e.url}
    });
    console.log(documentArray);
    return documentArray;
}

function validateUppy(uppyObj, key, label, fileMandatory) {

    if (!uppyObj.state || uppyObj.state.totalProgress == 0) {
        if (fileMandatory) {
            return {
                valid: false, key: key,
                msg: `${label} is required`
            };
        }
        return {valid: true};
    } else if (uppyObj.state.totalProgress < 100) {
        return {valid: false, key: key, msg: `${label} upload in Progress(अपलोड प्रगति पर है)`};
    } else {
        return {valid: true, key: key, url: Object.values(uppyObj.state.files)[0].uploadURL};
    }
}

function validmain() {
    let file = [
        validateUppy(aadharcarduppy, 'UID_FRONT', 'Aadhaar Card Frontside Picture (आधार कार्ड की फोटो)*', true),
        validateUppy(aadharcardbackuppy, 'UID_BACK', 'Aadhaar Card Backside Picture (आधार कार्ड की फोटो)*', true),
    ]

    if (!file.reduce((aggr, current) => {
        return current.valid && aggr
    }, true)) {
        let error = file.reduce((aggr, current) => {
            if (current.msg) {
                return aggr + '\n' + current.msg
            } else {
                return aggr
            }
        }, '');
        window.alert(error);
        return null;
    }
    let documentsRelationArray = file.filter(e => e.url).map(e => {
        return {type: e.key, link: e.url}
    });
    console.log(documentsRelationArray);
    return documentsRelationArray;
}

function gatherFamilyMembersData() {
    return $.map($('.familyMemberLineItem'), member => {

        var fields = [
            ...$.map($(member).find('.form-img-input'), (e) => {
                return {name: e.id, value: e.src}
            }),
            ...$(member).find('input,select').serializeArray()
        ];

        memberMap = fields.reduce(
            function (accum, item) {
                if (item.value !== null) {
                    accum[item.name.split('-')[1]] = item.value;
                }
                return accum;
            },
            {}
        );

        memberMap.additional_details = {
            profession: memberMap.profession,
            company_name: memberMap.company_name
        };

        return memberMap;

    });

}


function removeFamilyMemberFromDom(relation, ) {
    $(`.${relation}-familyMemberLineItem`).remove();
}

function addFamilyMember(relation_name, relation_label) {

    let relation_block = `<input type="hidden" name="${relation_name}-relation" value="${relation_name}"/>`

    let farilyBlockElement = `
    <div class="form-group mb-0 initialize familyMemberLineItem ${relation_name}-familyMemberLineItem">
        ${relation_block}
        <div class="border-bottom pt-2 pb-2">
            <input type="hidden" name="${relation_name}-ocr_processed"/>
           
            <div class="row m-0">
                <div class="col-sm-4">
                    <div class="">
                        <p>${relation_label} का नाम (Name)<strong style="color:red">*</strong></p>
                        <input type="text" class="form-control aadhaar_ocr" id="${relation_name}-name"  name="${relation_name}-name" value="" required readonly/>
                    </div>
                </div>
                <div class="col-sm-4">
                    <p>${relation_label} का जन्म की तारीख (Date Of Birth) <strong style="color:red">*</strong></p>
                    <div class="">
                        <input type="date" class="form-control aadhaar_ocr" name="${relation_name}-dob" id="${relation_name}-dob" required readonly />
                    </div>
                </div>
                <div class="col-sm-4">
                    <p>${relation_label} का (Gender) <strong style="color:red">*</strong></p>
                    <div class="form-group ">
                        <select required class="selectpicker form-control" id="${relation_name}-gender" name="${relation_name}-gender" readonly>
                            <option value="" id="status" disabled>
                                --- Select Gender ---
                            </option>
                            <option value="male" disabled>Male</option>
                            <option value="female" disabled>Female</option>
                        </select>
                    </div>
                </div>
            </div>
            <div class="row m-0 mt-2">
                <div class="col-sm-4">
                    <p>${relation_label} का आधार संख्या (Aadhaar Number).<strong style="color:red">*</strong></p>
                    <div class="">
                        <input required maxlength="12" minlength="12" type="tel" class="aadhar_on_blur form-control aadhaar_ocr" name="${relation_name}-uid_no" id="${relation_name}-uid_no" pattern="[0-9]{12}" readonly>
                    </div>
                </div>
                <div class="col-sm-4">
                    <div class="">
                        <p>${relation_label} का पेशा (Profession)<strong style="color:red">*</strong></p>
                        <input type="text" class="form-control" id="${relation_name}-profession"  name="${relation_name}-profession" value="" required   />
                    </div>
                </div>
                <div class="col-sm-4">
                    <div class="">
                        <p>${relation_label} कंपनी का नाम (Industry Name)<strong style="color:red">*</strong>
                        </p>
                        <input type="text" class="form-control" id="${relation_name}-company_name"  name="${relation_name}-company_name" value="" required   />
                    </div>
                </div>
            </div>
            <div class="row ocr_aadhaar_img m-0 mt-2">
                <div class="col-sm-8">
                <ul>
                    <li>
                        <p>${relation_label} Aadhaar Front<strong style="color:red">*</strong></p>
                            <img class="form-img-input" id="${relation_name}-uid_front_link">
                    </li>
                    <li>
                        <p>${relation_label} Aadhaar Back<strong style="color:red">*</strong></p>
                            <img class="form-img-input" id="${relation_name}-uid_back_link">
                    </li>
                    </ul>
                </div>
                <div class="col-sm-4 mt-2">
                    <div class="">
                        <button type="button" class="btn btn-primary float-right"
                        onclick="family_member_service.update_fm_via_ocr('${relation_name}')">
                            Upload Aadhaar
                        </button>
                    </div>
                </div>
            </div>
            <div class="row m-0 mt-2">
                <div class="col-sm-4">
                    <div class="">
                        <!-- Add delete button -->
                        <button type="button" class="btn btn-danger delete_${relation_name}" onclick="removeFamilyMemberFromDom('${relation_name}')">
                            Delete ${relation_label}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    `;
    $('#family_members_tree').append($(farilyBlockElement));
}

//aadhaar check
function checkApplicantsAadhaarValidity(uid_data) {
    return new Promise((resolve, reject) => {
        var uid = uid_data.aadhaar.value;

        if(!validateAadhaar(uid)) {
            return reject("Invalid aadhaar, please check again.");
        }
        if($('#family_members_tree .aadhar_on_blur').get().map((e)=> e.value).indexOf(uid) >= 0) {
            return reject("Aadhaar already entered in Family Members List");
        }

        jQuery.ajax({
            url: '/ujjwala/ujjwala-application/check_uid/',
            type: "GET",
            data: {'uid': uid},
            success: function (data) {
                response = data;
                if (response.status === true) {
                    $("#self-uid-msg").html('<p style=" color:green; "> ✔ आप आवेदन कर सकते है। </p>');
                    return resolve(uid_data);
                }

                // msg = data.data.applications.map(e=>`<p>आपका आवेदन पहले से मौजूद है ${e.id} Name: ${e.name}</p>`).join('');
                // $("#self-uid-msg").html(msg).css({'color': 'red', 'font-size' : '17px'});

                return reject(`ID: ${data.data.applications[0].id} Name: ${data.data.applications[0].name}`);
            },
        });
    });
}


// The multiplication table
var d = [
[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
[1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
[2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
[3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
[4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
[5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
[6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
[7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
[8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
[9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
];
// permutation table p
var p = [
[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
[1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
[5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
[8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
[9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
[4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
[2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
[7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
];
// inverse table inv
var inv = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9];

// generates checksum
function generate(array) {
    var c = 0;
    var invertedArray = array.reverse();
    for (var i = 0; i < invertedArray.length; i++) {
        c = d[c][p[((i + 1) % 8)][invertedArray[i]]];
    }
    return inv[c];
}

function validateAadhaar(aadhaarString) {
    if (aadhaarString.length != 12) {
        return false;
    }
    if (aadhaarString.match(/[^$,.\d]/)) {
        return false;
    }
    var aadhaarArray = aadhaarString.split('');
    var toCheckChecksum = aadhaarArray.pop();
    if (generate(aadhaarArray) == toCheckChecksum) {
        return true;
    } else {
        return false;
    }
}



$(document).ready(function() {
    let setMaritalStatus = '';
    let setOccupancyStatus = '';

    $('#occupancy_status,#marital_status').on('change', function() {
        occupancy_status = $('#occupancy_status').val();
        marital_status = $('#marital_status').val();

        if (setMaritalStatus == marital_status && setOccupancyStatus == occupancy_status) return;
        setMaritalStatus = marital_status;
        setOccupancyStatus = occupancy_status;

        // removeAllFamilyMembersExceptSelf();

        if (setMaritalStatus == 'UNMARRIED' && occupancy_status == 'LIVING_WITH_FAMILY') {
            family_member_service.remove_fm('HUSBAND');
            family_member_service.add_fm('FATHER');
            family_member_service.add_fm('MOTHER');
        } else if (setMaritalStatus == 'MARRIED' && occupancy_status == 'LIVING_WITH_FAMILY') {
            family_member_service.remove_fm('FATHER');
            family_member_service.remove_fm('MOTHER');
            family_member_service.add_fm('HUSBAND');
        }
    });

});

