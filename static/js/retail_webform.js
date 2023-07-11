
function checkContactMobileValidity() {

    var mobile = $("#uid_linked_mobile").val();
    if($("#uid_linked_mobile" ).attr("validated_value")==mobile) return;

    $("#contact_mobile_detail").html('');
    if (!mobile){
        // document.getElementById("uid_linked_mobile").setCustomValidity("Invalid mobile number.");
        document.getElementById("uid_linked_mobile").reportValidity();
        // document.getElementById("uid_linked_mobile").focus();
        return;
    }

    if (!(mobile.match(/^[6789][0-9]{9}$/))){
        // document.getElementById("uid_linked_mobile").setCustomValidity("Invalid mobile number.");
        document.getElementById("uid_linked_mobile").reportValidity();
        // document.getElementById("uid_linked_mobile").focus();
        return;
    }
    $("#contact_mobile_detail").show();
    // $("#contact_mobile_detail").html('<img style="width:18px; margin-left:10px;" align="left">&nbsp;Checking Mobile...');

    $("#uid_linked_mobile" ).attr("validated_value", mobile);

    // jQuery.ajax({
    //     url: '/ujjwala/ujjwala-application/check_phone/',
    //     type: "GET",
    //     data: {'whatsapp_number': mobile},
    //     success: function (data) {
    //         // response = data;
    //         document.getElementById("uid_linked_mobile").reportValidity();
    //         if (response.status === true) {
    //             $("#contact_mobile_detail").show();
    //             $("#contact_mobile_detail").html('✔ Unique Mobile Number').css({'color': 'green', 'font-size' : '14px'});
    //             // document.getElementById("uid_linked_mobile").setCustomValidity("")
    //             document.getElementById("uid_linked_mobile").reportValidity();
    //             return true;
    //         } else {
    //             console.log(response);
    //             var datas = response.data;
    //             var msg = response.msg;
    //             // var status = response.status;
    //             // var applications = datas.applications;
    //             document.getElementById("uid_linked_mobile").reportValidity();
    //             $("#contact_mobile_detail").html(msg).css({'color': 'red', 'font-size' : '17px'});
    //         }
    //     },
    // });
};

function checkMobileValidity() {
    var mobile = $("#whatsapp_number").val();

    if($("#mobile_detail" ).attr("validated_value")==mobile) return;

    $("#mobile_detail").html('');
    if (!mobile){
        // document.getElementById("whatsapp_number").setCustomValidity("Invalid mobile number.");
        document.getElementById("whatsapp_number").reportValidity();
        // document.getElementById("whatsapp_number").focus();
        return;
    }

    if (!(mobile.match(/^[6789][0-9]{9}$/))){
        // document.getElementById("whatsapp_number").setCustomValidity("Invalid mobile number.");
        document.getElementById("whatsapp_number").reportValidity();
        // document.getElementById("whatsapp_number").focus();
        return;
    }
    $("#mobile_detail").show();
    // $("#mobile_detail").html('<img style="width:18px; margin-left:10px;" align="left"> Checking Mobile...');

    $("#mobile_detail" ).attr("validated_value", mobile);

    //Disable Dedup

    $('#verifyWhatsappButton').attr('disabled', true);

    // jQuessssss
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

    return true;

}

async function upload_sign_and_submit() {

    jQuery('#submit').html('Please wait...');
    jQuery('#submit').attr('disabled', true);
    submit_form()
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
    let addresses = [];

    let formdata = $('form').serializeArray(
    ).reduce((accum, item) => {
        if (-1 === ['ignoreThis', 'andThat'].indexOf(item.name)) {
            if (item.value !== null) {
                accum[item.name] = item.value;
            }
        }
        return accum;
    }, {});


    formdata.addresses = [{
        title: 'Main Address',
        shop_name: formdata.shop_name,
        floor: formdata.floor,
        street_no: formdata.street_no,
        landmark: formdata.landmark,
        pincode: formdata.pincode,
        locality: formdata.locality,
        city: formdata.city
    }];

    formdata.documents = documentArray;
    formdata.family_members = gatherFamilyMembersData();

    console.log(formdata);

    jQuery('#submit').html('Please wait...');
    jQuery('#submit').attr('disabled', true);


    jQuery.ajax({
        url: '/retail-customers/retail-customer/wf/',
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
            window.location.assign('/retail-customers/');
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
        validateUppy(gstuppy, 'GST_PHOTO', 'Customer Picture or Selfie', true),
        validateUppy(panuppy, 'PAN_PHOTO', 'pan Photo', true),
        validateUppy(mclicenseuppy, 'MCLICENSE_PHOTO', 'MCL License', true)
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
        return {valid: false, key: key, msg: `${label} upload in Progress`};
    } else {
        return {valid: true, key: key, url: Object.values(uppyObj.state.files)[0].uploadURL};
    }
}

function validmain() {
    let file = [
        validateUppy(aadharcarduppy, 'UID_FRONT', 'Aadhaar Card Frontside Picture*', true),
        validateUppy(aadharcardbackuppy, 'UID_BACK', 'Aadhaar Card Backside Picture*', true),
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

    });

}


function removeFamilyMemberFromDom(relation) {
    $(`.${relation}-familyMemberLineItem`).remove();
}

function addFamilyMember(relation_name, relation_label) {

    let relation_block = `<input type="hidden" name="${relation_name}-relation" value="${relation_name}"/>`

    let farilyBlockElement = `
    <div class="mb-0 initialize familyMemberLineItem ${relation_name}-familyMemberLineItem">
        ${relation_block}
            <input type="hidden" name="${relation_name}-ocr_processed"/>
           <div class="row ">
                <div class="col-12">
                   
                </div>
            </div>
            <div class="row m-0">
                <div class="col-sm-3">
                    <div class="">
                        <p>${relation_label} Name<strong style="color:red">*</strong></p>
                        <input type="text" class="form-control aadhaar_ocr" id="${relation_name}-name"  name="${relation_name}-name" value="" required readonly/>
                    </div>
                    
                </div>
                <div class="col-sm-3">
                        <p>${relation_label} Aadhaar Number <strong style="color:red">*</strong></p>
                        <input required maxlength="12" minlength="12" type="tel" class="aadhar_on_blur form-control aadhaar_ocr" name="${relation_name}-uid_no" id="${relation_name}-uid_no" pattern="[0-9]{12}" readonly>
                    </div>
                <div class="col-sm-3">
                    <button type="button" class="btn btn-primary float-left "
                    onclick="family_member_service.update_fm_via_ocr('${relation_name}')">
                        Upload Aadhaar
                    </button>
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

        // jQuery.ajax({
        //     url: '/ujjwala/ujjwala-application/check_uid/',
        //     type: "GET",
        //     data: {'uid': uid},
        //     success: function (data) {
        //         response = data;
        //         if (response.status === true) {
        //             $("#Customer-uid-msg").html('<p style=" color:green; "> ✔ Detail submitted </p>');
        //             return resolve(uid_data);
        //         }

        //         return reject(`ID: ${data.data.applications[0].id} Name: ${data.data.applications[0].name}`);
        //     },
        // });

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





