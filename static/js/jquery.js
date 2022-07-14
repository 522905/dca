
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
    $("#mobile_detail").html('<img style="width:18px; margin-left:10px;" align="left">&nbsp;Checking Mobile...');

    $("#mobile_detail" ).attr("validated_value", mobile);

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
    if(pincode && pincode >= 141001 && pincode <= 141014) {
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

    if ($('[id="applicant-uid_no"]').val() != $('[id="SELF-uid_no"]').val()) {
        alert("Applicant UID mismatch, please enter UID again");
        return false;
    }
    return true;

}

function validate_terms_condtions(){
    if(!$('#term_condition_agree').is(':checked')){
        alert("Please read the terms and then tick the check box. कृपया शर्तें पढ़ लीजिए ओर फिर चेक बॉक्स पर टिक कीजिए |");
        return false;
    }
    return true;
}

function upload_sign_and_submit() {
    if(!$('#form')[0].reportValidity()) {
        alert("Please complete all required fields");
        return;
    }

    if (!validate_pincode()) {
        return;
    }

    if (!validate_terms_condtions()) {
        return;
    }

    if(!validateAadhaarrUniquness()) {
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
    let formdata = $('form').serializeArray()
        .reduce(function (accum, item) {

                if (-1 === ['ignoreThis', 'andThat'].indexOf(item.name)) {

                    if (item.value !== null) {
                        accum[item.name] = item.value;
                    }
                }
                return accum;
            },
            {}
        );

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
            jQuery('#submit').html('Submit');
            jQuery('#submit').attr('disabled', false);
        }

    });
}

function valid() {
    let files = [
        validateUppy(customerpictureuppy, 'CUSTOMER_PHOTO', 'Customer Picture or Selfie (ग्राहक की फोटो)*', false),
        validateUppy(bankdetailuppy, 'BANK_DETAIL', 'Bank Detail (पास बुक का विवरण)', false)
    ]

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

function validateFamilyMembersFiles() {

    members = $.map($('.familyMemberLineItem'), member => {

        return $(member).find('input,select').serializeArray().reduce(
            function (accum, item) {
                if (item.value !== null) {
                    accum[item.name.split('-')[1]] = item.value;
                }
                return accum;
            },
            {}
        );

    })


    file_list_front = $.map(members, memberMap =>
        validateUppy(window[`${memberMap.relation}-uid_front_link_uppy`], 'UID_FRONT', `${memberMap.relation} Aadhaar Card Frontside Picture (आधार कार्ड की फोटो)*`, true),
        validateUppy(window[`${memberMap.relation}-uid_front_link_uppy`], 'FATHER_UID_FRONT', `${memberMap.relation}Father Aadhaar Card Frontside Picture (आधार कार्ड की फोटो)*`, true)
    );

    file_list_back = $.map(members, memberMap =>
        validateUppy(window[`${memberMap.relation}-uid_back_link_uppy`], 'UID_BACK', `${memberMap.relation} Aadhaar Card Backside Picture (आधार कार्ड की फोटो)*`, true),
        validateUppy(window[`${memberMap.relation}-uid_back_link_uppy`], 'FATHER_UID_FRONT', `${memberMap.relation}Father Aadhaar Card Frontside Picture (आधार कार्ड की फोटो)*`, true)
    );

    files = file_list_front.concat(file_list_back);

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

}

function gatherFamilyMembersData() {
    return $.map($('.familyMemberLineItem'), member => {

        memberMap = $(member).find('input,select').serializeArray().reduce(
            function (accum, item) {
                if (item.value !== null) {
                    accum[item.name.split('-')[1]] = item.value;
                }
                return accum;
            },
            {}
        );

        memberMap.uid_front_link = Object.values(window[`${memberMap.relation}-uid_front_link_uppy`].state.files)[0].uploadURL;
        memberMap.uid_back_link = Object.values(window[`${memberMap.relation}-uid_back_link_uppy`].state.files)[0].uploadURL;

        memberMap.additional_details = {
            profession: memberMap.profession,
            company_name: memberMap.company_name
        };

        return memberMap;

    });

}

function removeAllFamilyMembersExceptSelf() {
    $.each($('.familyMemberLineItem'), (index, member) => {

        memberMap = $(member).find('input').serializeArray().reduce(
            function (accum, item) {
                if (item.value !== null) {
                    accum[item.name.split('-')[1]] = item.value;
                }
                return accum;
            },
            {}
        );
        delete window[`${memberMap.relation}-uid_front_link_uppy`];
        delete window[`${memberMap.relation}-uid_back_link_uppy`];

    });

    $('#family_members_tree').html('');
}

function addFamilyMember(relation_name, relation_label) {

    let relation_block = `<input type="hidden" name="${relation_name}-relation" value="${relation_name}"/>`

    let farilyBlockElement = `

    <div class="form-group initialize familyMemberLineItem">
        ${relation_block}
        <div class="card m-2 pb-4 pt-2">
            <div class="row m-0 pl-sm-2">
                <div class="col-sm-4">
                    <div class="">
                        <p>${relation_label} Name<strong style="color:red">*</strong></p>
                        <input type="text" class="form-control" id="${relation_name}-name"  name="${relation_name}-name" value="" required   />
                    </div>
                </div>
                <div class="col-sm-4">
                    <p>${relation_label} Date Of Birth<strong style="color:red">*</strong></p>
                    <div class="">
                        <input type="date" class="form-control" name="${relation_name}-dob" id="${relation_name}-dob" required></input>
                    </div>
                </div>
                <div class="col-sm-4">
                    <p>${relation_label} Aadhaar No.<strong style="color:red">*</strong></p>
                    <div class="">
                        <input required maxlength="12" minlength="12" type="tel" class="aadhar_on_blur form-control" name="${relation_name}-uid_no" id="${relation_name}-uid_no"  pattern="[0-9]{12}"></input>
                    </div>
                </div>
            </div>
            <div class="row m-0 pl-4 pt-3 mt-4">
                <div class="col-sm-4">
                    <div>
                        <p>${relation_label} Aadhaar Card Front Photo (आधार कार्ड की फोटो)<strong
                                style="color:red">*</strong></p>
                        <span class="custom-file-input" name="${relation_name}-uid_front_link" id="${relation_name}-uid_front_link">
                        </span><br>
                    </div>
                </div>
                <div class="col-sm-4">
                    <div class="">
                        <p>${relation_label} Aadhaar Card Back Photo (आधार कार्ड की फोटो)<strong style="color:red">*</strong>
                        </p>
                        <span class="custom-file-input" name="${relation_name}-uid_back_link" id="${relation_name}-uid_back_link">
                        </span><br>
                    </div>
                </div>
                <div class="col-sm-4">
                    <div class="">
                        <p>${relation_label} Profession(पेशा)<strong style="color:red">*</strong>
                        </p>
                        <input type="text" class="form-control" id="${relation_name}-profession"  name="${relation_name}-profession" value="" required   />
                    </div>
                </div>
            </div>

            <div class="row m-0 pl-4 pt-3 mt-4">
                <div class="col-sm-4">
                    <div class="">
                        <p>${relation_label} Industry Name(कंपनी का नाम)<strong style="color:red">*</strong>
                        </p>
                        <input type="text" class="form-control" id="${relation_name}-company_name"  name="${relation_name}-company_name" value="" required   />
                    </div>
                </div>
            </div>
        </div>
    </div>
    `;

    $('#family_members_tree').append($(farilyBlockElement));

    setTimeout(() => {
        initUppyUpload(`${relation_name}-uid_back_link`, `${relation_name}-uid_back_link_uppy`);
        initUppyUpload(`${relation_name}-uid_front_link`, `${relation_name}-uid_front_link_uppy`);
    }, 0);

}

function initUppyUpload(elementId, elementVariable) {

    window[elementVariable] = new Uppy.Core({
        debug: true,
        autoProceed: true,
        restrictions: {
            maxFileSize: 50000000,
            maxNumberOfFiles: 1,
            minNumberOfFiles: 1,
            allowedFileTypes: ['image/*'],
        }
    })
        .use(Uppy.Dashboard, {
            trigger: `#${elementId}`,
            inline: true,
            target: `#${elementId}`,
            showProgressDetails: true,
            note: 'Image, 1 file, up to 10 MB',
            height: 40,
            metaFields: [],
            id: elementId,
            browserBackButtonClose: false
        })
        .use(Uppy.Tus, {
            endpoint: 'https://tus.dca.arungas.com/files/',
        });

}


//aadhaar check 
function checkApplicantsAadhaarValidity() {
    var e = document.getElementById('applicant-uid_no');
    var uid = e.value;
    if($("#applicant-uid_no" ).attr("validated_value")==uid) return;
    
    if(!validateAadhaar(uid)) {
        e.setCustomValidity("Invalid aadhaar, please check again.");
    } else {
        if($('#family_members_tree .aadhar_on_blur:not([id="SELF-uid_no"]').get().map((e)=> e.value).indexOf(uid) >= 0) {
            e.setCustomValidity("Aadhaar already entered in Family Members List");
        } else {
            $("#self-uid-msg").html('Checking Aadhaar...');

            $("#applicant-uid_no" ).attr("validated_value", uid);

            jQuery.ajax({
                url: '/ujjwala/ujjwala-application/check_uid/',
                type: "GET",
                data: {'uid': uid},
                success: function (data) {
                    response = data;
                    if (response.status === true) {
                        e.setCustomValidity("");
                        $('#family_members_tree [id="SELF-uid_no"]').val(uid);
                        $("#self-uid-msg").html('<p style=" color:green; "> ✔ आप आवेदन कर सकते है। </p>');
                    } else {
                        e.setCustomValidity(`ID: ${data.data.applications[0].id} Name: ${data.data.applications[0].name}`);
                        e.focus();

                        msg = data.data.applications.map(e=>`<p>आपका आवेदन पहले से मौजूद है ${e.id} Name: ${e.name}</p>`).join('');
                        $("#self-uid-msg").html(msg).css({'color': 'red', 'font-size' : '17px'});

                    }
                },
            });
        }
    }
    e.reportValidity();
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

    $('#customername').on('blur', function() {
        if (document.getElementById("SELF-name") != null) {
            $('#SELF-name').val($('#customername').val());
        }
    });

    $('#occupancy_status,#marital_status').on('change', function() {
        occupancy_status = $('#occupancy_status').val();
        marital_status = $('#marital_status').val();

        if (setMaritalStatus == marital_status && setOccupancyStatus == occupancy_status) return;
        setMaritalStatus = marital_status;
        setOccupancyStatus = occupancy_status;

        removeAllFamilyMembersExceptSelf();
        addFamilyMember('SELF', 'Self');

        if (setMaritalStatus == 'UNMARRIED' && occupancy_status == 'LIVING_WITH_FAMILY') {
            addFamilyMember('FATHER', 'Father');
            addFamilyMember('MOTHER', 'Mother');
        } else if (setMaritalStatus == 'MARRIED' && occupancy_status == 'LIVING_WITH_FAMILY') {
            addFamilyMember('HUSBAND', 'Husband');
        }
        $('#family_members_tree [id="SELF-uid_no"]').attr("readonly", true);
        
        $('#family_members_tree [id="SELF-uid_no"]').val(
            $('input[id="applicant-uid_no"]').val()
        );

    });

    // $('#uid_mobile_status').change(function() {
    //     $(this).find("option:selected").each(function() {
    //         var optionValue = $(this).attr("value");

    //         if (optionValue === 'LINKED_WITH_SAME_MOBILE') {
    //             $("#uid_linked_mobile_form_group").show();
    //             $("#uid_linked_mobile").val($("#contact_mobile").val());
    //             $('#uid_linked_mobile').prop('disabled', true);
    //         } else if (optionValue == 'MOBILE_NOT_AVAILABLE') {
    //             $("#uid_linked_mobile_form_group").hide();
    //             $('#uid_linked_mobile').prop('disabled', true);
    //         } else {
    //             $('#uid_linked_mobile').prop('disabled', false);
    //             $("#uid_linked_mobile_form_group").show();
    //         }

    //     });
    // }).change();

    window.bankdetailuppy = new Uppy.Core({
        debug: true,
        autoProceed: true,
        restrictions: {
            maxFileSize: 50000000,
            maxNumberOfFiles: 1,
            minNumberOfFiles: 1,
            allowedFileTypes: ['image/*'],
        }
    })
    .use(Uppy.Dashboard, {
        trigger: '#bankdetail',
        inline: true,
        target: '#bankdetail',
        showProgressDetails: true,
        note: 'Images only, 1 file, up to 10 MB',
        height: 250,
        metaFields: [],
        id: 'bankdetail',
        browserBackButtonClose: false
    })
    .use(Uppy.Tus, {
        endpoint: 'https://tus.dca.arungas.com/files/',
    })
    
    bankdetailuppy.on('complete', result => {
        console.log('successful files:', result.successful)
        console.log('failed files:', result.failed)
    });


    $('#family_members_tree').on("blur", ".aadhar_on_blur", function() {
        var e = this
        var uid = this.value;
    
        if(!validateAadhaar(e.value)) {
            this.setCustomValidity("Invalid aadhaar, please check again.");
        } else {
            if($(`#family_members_tree .aadhar_on_blur:not([id="${e.getAttribute('id')}"])`).get().map((i)=> i.value).indexOf(uid) >= 0) {
                    this.setCustomValidity("Aadhaar already entered in Family Members List");
            } else {
                jQuery.ajax({
                    url: '/ujjwala/ujjwala-application/check_uid/',
                    type: "GET",
                    data: {'uid': uid},
                    success: function (data) {
                        response = data;
    
                        if (response.status === true) {
                            e.setCustomValidity("");
                        } else {    
                            e.setCustomValidity(data.msg);
                            e.focus();
                        }
                    },
                });
            }
        }
    
        e.reportValidity();
    
    });
    
    $('#menu').find('li').click(function(){
        //removing the previous selected menu state
        $('#menu').find('li').removeClass('active');
         
         //is this element from the second level menu?
         if($(this).closest('ul').hasClass('secondLevel')){
              $(this).parents('li').addClass('active');
             
         //this is a parent element
         }else{
              $(this).addClass('active');
         }
     });


});

