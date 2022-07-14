function ensureLocationAccess() {
    navigator.geolocation.getCurrentPosition(
        ()=>{},
        (error)=>{
            if (error.code == 1) {
                debugger
                let locationBlockElement = `
                    <div class="overlay_location_outer">
                        <p style="font-size: 20px; color:#fff; padding-top:30px; margin:20px; text-align: center;"> निचे दिए गए बटन पर क्लिक करे और लोकेशन को ओपन करें <br>ताकि प्री-सुरक्षा-ड्रिल की 
                            प्रक्रिया पूरा किया जा सके|</p>
                        <a target="_blank" class="btn btn-primary" href="https://arungas.com/public/ujwalla/chrome-location-guide.pdf">Chrome Location Guide</a>
                        <a target="_blank" class="btn btn-primary" href="https://arungas.com/public/ujwalla/app-location-guide.pdf">App Location Guide</a>
                        <p>अगर दोनों जगह लोकेशन ऑन करने के बाद भी न चले तो क्रोम ब्राउज़र की लोकेशन में जा कर ब्लॉक लिस्ट चेक करे, और वहा से ब्लॉक लिस्ट से निकले|</p>
                    </div>
                `;
                $('#add_location').append($(locationBlockElement));
            }
        },
        {maximumAge:600000, timeout:10000, enableHighAccuracy: true}
    );

}
// for location
function allowLocationNav() {
    navigator.geolocation.getCurrentPosition(
        successCallback,
        errorCallback_highAccuracy,
        {maximumAge:600000, timeout:5000, enableHighAccuracy: true}
    );
}

function errorCallback_highAccuracy(error) {
    if (error.code == error.TIMEOUT) {
        // Attempt to get GPS loc timed out after 5 seconds, 
        // try low accuracy location
        $('#map_error_msg').append("attempting to get low accuracy location");
        navigator.geolocation.getCurrentPosition(
            successCallback, 
            errorCallback_lowAccuracy,
            {maximumAge:600000, timeout:10000, enableHighAccuracy: false});
        return;
    }
    
    var msg = "<p>Can't get your location (high accuracy attempt). Error = ";
    if (error.code == 1)
        msg += "PERMISSION_DENIED";
    else if (error.code == 2)
        msg += "POSITION_UNAVAILABLE";
    msg += ", msg = "+error.message;
    
    $('#map_error_msg').append(msg);
    $('body').attr('id', 'add_location');
}

function errorCallback_lowAccuracy(error) {
    var msg = "<p>Can't get your location (low accuracy attempt). Error = ";
    if (error.code == 1)
        msg += "PERMISSION_DENIED";
    else if (error.code == 2)
        msg += "POSITION_UNAVAILABLE";
    else if (error.code == 3)
        msg += "TIMEOUT";
    msg += ", msg = "+error.message;
    
    $('#map_error_msg').append(msg);
    $('body').attr('id', 'add_location');
}

function successCallback(position) {
    var latitude = position.coords.latitude;
    var longitude = position.coords.longitude;

    var meter = Math.round(position.coords.accuracy);

    if (meter > 300) {
        $('#map_error_msg').append("<p>किसी खुले क्षेत्र में जाएं और स्थान को फिर से कैप्चर करें। Move to an open area and capture location again. Location accuracy not precise enough! </p>");
        return;
       
    }

    $('#map_error_msgs').append("<p>Your location is: " + latitude + "," + longitude+" </p><p>Accuracy="+meter+"m");
    $('#id_latitude').val(latitude);
    $('#id_longitude').val(longitude);
    $('#id_accuracy').val(meter + 'm');
    console.log(successCallback);
    
}









