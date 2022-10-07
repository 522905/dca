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
                $('#add_location').html($(locationBlockElement));
            }
        },
        {maximumAge:600000, timeout:10000, enableHighAccuracy: true}
    );

}

let pendingLocationAttempts = 6;
let locationTimeouts = {
    6: 10 * 1000,
    5: 12 * 1000,
    4: 15 * 1000,
    3: 20 * 1000,
    2: 25 * 1000,
    1: 30 * 1000
}

// for location
function allowLocationNav() {
    timeout = locationTimeouts[pendingLocationAttempts] || 10 * 1000;
    navigator.geolocation.getCurrentPosition(
        successCallback,
        errorCallback_highAccuracy,
        {maximumAge:600000, timeout: timeout, enableHighAccuracy: true}
    );
}

function reattemptLocationFetch() {
    pendingLocationAttempts = pendingLocationAttempts - 1;

    if (pendingLocationAttempts<= 0) {
        $('#map_error_msg').html(
            `लोकेशन कैप्चर करने के सभी प्रयास असफल रहे, किसी खुले क्षेत्र में जाएं और लोकेशन को फिर से कैप्चर करें`
        );    
        return;
    }

    timeout = locationTimeouts[pendingLocationAttempts] || 10 * 1000;

    $('#map_error_msg').html(
        `${pendingLocationAttempts}कम लोकेशन प्राप्त करने का प्रयास `
    );

    navigator.geolocation.getCurrentPosition(
        successCallback,
        errorCallback_highAccuracy,
        {maximumAge:600000, timeout: timeout, enableHighAccuracy: true}
    );
}

function errorCallback_highAccuracy(error) {
    if (error.code == error.TIMEOUT) {
        reattemptLocationFetch();
        return;
        // navigator.geolocation.getCurrentPosition(
        //     successCallback, 
        //     () => {},
        //     {maximumAge:600000, timeout:10000, enableHighAccuracy: false});
        // return;
    }
    
    var msg = "<p>आपका लोकेशन नहीं मिल रहा है (सही लोकेशन प्राप्त करने का प्रयास). Error = ";
    if (error.code == 1)
        msg += "PERMISSION_DENIED";
    else if (error.code == 2)
        msg += "POSITION_UNAVAILABLE";
    msg += ", msg = "+error.message;
    
    $('#map_error_msg').html(msg);
    $('body').attr('id', 'add_location');
}

// function errorCallback_lowAccuracy(error) {
//     var msg = "<p>आपका लोकेशन नहीं मिल रहा है (कम सटीकता का प्रयास). Error = ";
//     if (error.code == 1)
//         msg += "PERMISSION_DENIED";
//     else if (error.code == 2)
//         msg += "POSITION_UNAVAILABLE";
//     else if (error.code == 3)
//         msg += "TIMEOUT";
//     msg += ", msg = "+error.message;
//     $('#map_error_msgs').html("<p>Your location is: " + latitude + "," + longitude+" </p><p>Accuracy="+meter+"m");
//     $('#map_error_msg').html(msg);
//     $('body').attr('id', 'add_location');
// }

function successCallback(position) {
    var latitude = position.coords.latitude;
    var longitude = position.coords.longitude;
    var meter = Math.round(position.coords.accuracy);
    window.deviceLocation = {lat: latitude, lng: longitude, accuracy: meter}

    initMap(window.deviceLocation.lat, window.deviceLocation.lng, window.deviceLocation.accuracy);

    const cityCircle = new google.maps.Circle({
      strokeColor: "#FF0000",
      strokeOpacity: 0.8,
      strokeWeight: 2,
      fillColor: "#00FF00",
      fillOpacity: 0.10,
      map: map_obj,
      center: { lat: window.deviceLocation.lat, lng: window.deviceLocation.lng },
      radius: window.deviceLocation.accuracy,
    });
    map_obj.fitBounds(cityCircle.getBounds());
    console.log(successCallback);

}


//:::  Passed to function:                                                    :::
//:::    lat1, lon1 = Latitude and Longitude of point 1 (in decimal degrees)  :::
//:::    lat2, lon2 = Latitude and Longitude of point 2 (in decimal degrees)  :::
//:::    unit = the unit you desire for results                               :::
//:::           where: 'M' is statute miles (default)                         :::
//:::                  'K' is kilometers                                      :::
//:::                  'N' is nautical miles                                  :::
//:::                                                                         :::
function distance(lat1, lon1, lat2, lon2, unit) {
    if ((lat1 == lat2) && (lon1 == lon2)) {
        return 0;
    }
    else {
        var radlat1 = Math.PI * lat1/180;
        var radlat2 = Math.PI * lat2/180;
        var theta = lon1-lon2;
        var radtheta = Math.PI * theta/180;
        var dist = Math.sin(radlat1) * Math.sin(radlat2) + Math.cos(radlat1) * Math.cos(radlat2) * Math.cos(radtheta);
        if (dist > 1) {
            dist = 1;
        }
        dist = Math.acos(dist);
        dist = dist * 180/Math.PI;
        dist = dist * 60 * 1.1515;
        if (unit=="K") { dist = dist * 1.609344 }
        if (unit=="N") { dist = dist * 0.8684 }
        return dist;
    }
}
