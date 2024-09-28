# ujjwala view changes for pre inspection and status
import json, os,requests
from tusclient import client
import django_rq
from django.http import HttpResponse, Http404, HttpResponseRedirect, JsonResponse
from ujjwala.models import UjjwalaV2Application, PreInspection, ConnectionDisbursement, \
    FamilyMembers, DisbursementDrive, UjjwalaSearchLog, ConnectionDisbursementInvitation, BankDetailsUpdateRequest, \
    ChangeCylinderTypeRequest
from ujjwala.ujjwala_functions import ujjwala_application_reject_reason_log, is_pre_inspection_applicable
def upload_images_TusServer(file_url):
    if not file_url:
        return JsonResponse({"error": "No file URL provided"}, status=400)

    try:
        response = requests.get(file_url, stream=True)
        response.raise_for_status()  # Check if the request was successful

        # Extract the filename from the URL or generate one
        file_name = file_url.split('/')[-1] if file_url.split('/')[-1] else "downloaded_file"

        logs_dir = '/tmp'
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        # Step 2: Save the file temporarily in the /logs/ directory
        temp_file_path = os.path.join(logs_dir, file_name)
        with open(temp_file_path, 'wb') as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)

        # Step 3: Upload the file to TUSD server using tus-py-client
        tus_client_instance = client.TusClient('https://tus.dca.arungas.com/files/')
        uploader = tus_client_instance.uploader(temp_file_path, chunk_size=5242880)  # 5MB chunk size
        uploader.upload()

        os.remove(temp_file_path)

        return JsonResponse({"link": uploader.url, "status": True}, status=200)

    except requests.exceptions.RequestException as e:
        return JsonResponse({"error": f"Failed to download the file: {str(e)}"}, status=500)

    except Exception as e:
        return JsonResponse({"error": f"Failed to upload the file: {str(e)}"}, status=500)


def WhatsappPreInspection(Inspection_data, unique_id, intent):
    conn = django_rq.get_connection("default")
    dataSet = {
        "kitchen-photo": None,
        "address_details": None,
        "pin-location": None,
        "main-gate": None,
        "complete": False
    }
    if not unique_id and Inspection_data is None:
        return
    # Fetch the application using the unique ID
    application = UjjwalaV2Application.objects.filter(contact_mobile=unique_id).first()
    if not application:
        return f"इस फोन नंबर {unique_id} के साथ कोई आवेदन मौजूद नहीं है।"

    # Check if pre-inspection is applicable
    if not is_pre_inspection_applicable(application.id):
        return "आप प्री-निरीक्षण के लिए पात्र नहीं हैं। कृपया अपने आवेदन की स्थिति जांचें।"

    redis_data = conn.get(unique_id)
    if redis_data:
        dataSet = json.loads(redis_data)

    # Update the Redis data based on intent
    if intent == "kitchen-photo":
        link = conn.get(Inspection_data).decode("utf-8")
        if not link:
            return "Kitchen photo link not found in Inspection data."
        Tus_url = upload_images_TusServer(link)
        Tus_data = json.loads(Tus_url.content)

        if Tus_data.get("status") != True:
            return "Kitchen photo link not found"
        dataSet["kitchen-photo"] = Tus_data.get("link")
        print(f"the current updated data is {dataSet}")
        conn.delete(Inspection_data)
        conn.set(unique_id, json.dumps(dataSet))
        return "आपकी रसोई की फोटो अपडेट हो गई है, कृपया पता अपडेट के लिए नीचे दिया गया फॉर्म भरें।"

    if intent == "pin-location":
        dataSet["pin-location"] = Inspection_data
        conn.set(unique_id, json.dumps(dataSet))
        return "आपकी पिन लोकेशन का डेटा अपडेट हो गया है, अब कृपया Verification के लिए अपनी रसोई वाली फोटो साझा करें।"

    if intent == "main-gate":
        link = conn.get(Inspection_data).decode("utf-8")
        if not link:
            return "Kitchen photo link not found in Inspection data."

        Tus_url = upload_images_TusServer(link)
        Tus_data = json.loads(Tus_url.content)

        if Tus_data.get("status") != True:
            return "Kitchen photo link not found"
        dataSet["main-gate"] = Tus_data.get("link")
        print(f"the current updated data is {dataSet} ")
        conn.delete(Inspection_data)
        conn.set(unique_id, json.dumps(dataSet))
        return "आपके मुख्य द्वार की फोटो अपडेट हो गई है, अब कृपया ऊपर दिए गए वीडियो को देखकर अपनी पिन लोकेशन साझा करें।"

    if intent == "address_details":
        Inspection_data["update_address"] = True
        dataSet["address_details"] = Inspection_data
        dataSet["complete"] = True
        conn.set(unique_id, json.dumps(dataSet))
        # Trigger the submission method if 'complete' is True
        if dataSet["complete"]:
            return Follow_Set_Submission(conn, unique_id)

    return "Invalid intent provided."


def Follow_Set_Submission(conn, unique_id):
    try:
        # Retrieve the data from Redis
        redis_data = conn.get(unique_id)
        if not redis_data:
            return f"No data found for unique_id: {unique_id}"

        # Load the data and check if 'complete' is True
        data = json.loads(redis_data)
        if data.get("complete"):
            # Perform the operation to store data in the database
            location_data = json.loads(data.get("pin-location"))
            latitude = location_data.get('latitude')
            longitude = location_data.get('longitude')
            application = UjjwalaV2Application.objects.filter(contact_mobile=unique_id).first()
            if not application:
                return f"इस फोन नंबर {unique_id} के साथ कोई आवेदन मौजूद नहीं है।"

            pi_obj = PreInspection.objects.filter(parent_id=application.id).first()
            if not pi_obj:
                return "आप प्री-निरीक्षण के लिए पात्र नहीं हैं। कृपया अपने आवेदन की स्थिति जांचें।"

            # Initialize all forms
            form1 = ChangeAddressForm(pre_inspection=pi_obj, data=data["address_details"])
            form2 = KitchenPreInspectionForm(pre_inspection=pi_obj, data={"kitchen_photo": data["kitchen-photo"]})
            form3 = PreviewPreInspectionForm(pre_inspection=pi_obj, data={
                'main_gate': data["main-gate"],
                'longitude': longitude,
                'latitude': latitude
            })

            # List of all forms to validate
            forms = [form1, form2, form3]

            # Check validity of all forms at once
            all_valid = all(form.is_valid() for form in forms)

            if all_valid:
                # Save all forms if they are valid
                form1.save()
                form2.save()
                form3.save()
                print("All forms successfully saved.")
            else:
                # Gather error messages from invalid forms
                errors = []
                if not form1.is_valid():
                    errors.append("Address details form failed: " + str(form1.errors))
                if not form2.is_valid():
                    errors.append("Kitchen photo form failed: " + str(form2.errors))
                if not form3.is_valid():
                    errors.append("Preview form failed: " + str(form3.errors))

                # Return the error messages
                print(" | ".join(errors))

            # Remove the key from Redis after successful submission
            conn.delete(unique_id)
            return f"{unique_id} के लिए प्री-सुरक्षा सफलतापूर्वक सबमिट कर दी गई है और शीघ्र ही इसकी समीक्षा की जाएगी"
        else:
            return "प्री-सुरक्षा सबमिशन सफल नहीं हुआ, कृपया 2 भेजकर प्रक्रिया को पुनः आरंभ करें"
    except Exception as e:
        print(f"Error during Follow_Set_Submission: {e}")
        return "An error occurred during data submission."


def check_ujjwala_status(contact_mobile):
    if not contact_mobile:
        return JsonResponse({"error": "Phone number is required."}, status=400)

    # Retrieve the application based on the provided contact mobile number
    # application = UjjwalaV2Application.objects.get(pk=43857)
    application = UjjwalaV2Application.objects.filter(
        Q(contact_mobile=contact_mobile) | Q(sdms_mobile_number=contact_mobile)
    ).first()
    print(f"the object application is {application}")
    if not application:
        return 'No application found for the provided phone number'

    # Fetch the rejection reason if applicable
    if 'reject' in application.status.lower():
        reject_reason = ujjwala_application_reject_reason_log(application.id)
        if reject_reason is not None:
            return f"Application rejected: {reject_reason}"

    # Check for PreInspection object
    pi_obj = PreInspection.objects.filter(parent_id=application.id).first()
    from ujjwala.enums import PreInspectionRejectionReasonsEnum
    # check for rejected status of pi
    if pi_obj.status == "REJECTED":
        inspection_app_content_type = ContentType.objects.get(model=PreInspection.__name__.lower(), app_label="ujjwala")

        description = StateLog.objects.filter(
            object_id=pi_obj.id, content_type=inspection_app_content_type,
            state__icontains='reject'
        ).order_by('-id').first()
        if description:
            try:
                json_text = json.loads(description.description).get("reason")[0]
            except:
                return description.description
            print(json_text[0], json_text)

            status_dict = dict(PreInspectionRejectionReasonsEnum.choices)
            print(f"the dict value we get {status_dict.get(json_text, 'not able to access')} and {status_dict}")
        return f"your application has been rejected due to {status_dict.get(json_text) or 'wrong details'}"

    # Handle different statuses for PreInspection
    if pi_obj.status in ["ALLOCATED", "OTP_VERIFIED", "CHANGE_ADDRESS", "KITCHEN_PHOTO", "PREVIEW_INSPECTION"]:
        return "आपकी pre सुरक्षा अधूरी है. कृपया इस लिंक पर जाएँ और इसे पूरा करें। "

    if pi_obj.status == "SUBMITTED":
        return "आपकी प्री-सुरक्षा का सत्यापन चल रहा है।"

    # Fetch ConnectionDisbursement object
    connection = ConnectionDisbursement.objects.filter(parent=application.id).first()
    if connection is None:
        return 'No connection disbursement data found'

    if pi_obj.status == "ACCEPTED" and connection.status == "LEGAL_DOCUMENTS_PENDING":
        return "कृपया अपनी pre-सुरक्षा पूरी करने के लिए हस्ताक्षरित एबीसी फॉर्म इस लिंक पर अपलोड करें।"

    if connection.status == "LEGAL_DOCUMENTS_ACCEPTED" and not application.ekyc_cleared:
        return "कृपया एबीसी फॉर्म के साथ अरुण गैस पर जाएँ और अपना ईकेवाईसी सत्यापन पूरा करें।"

    # # Handle application-level statuses
    # if application.status == "OMC_REJECTED":
    #     return "Your family member has a linked connection with another distributor. Please resolve this issue first."

    if application.status == "READY_FOR_DISBURSEMENT":
        return "आप यह जानने के लिए हमें कॉल कर सकते हैं कि आपको अपना कनेक्शन सिलेंडर लेने के लिए कब आना है।"

    if application.status == "MATERIAL_DELIVERED":
        return "आपका सिलेंडर डिलीवर हो गया है, किसी भी प्रश्न के लिए हेल्प लाइन नंबर पर कॉल करें।"

    return "स्थिति पहचानी नहीं गई. कृपया अधिक सहायता के लिए समर्थन से संपर्क करें।"


# the ujjwala_forms changes for whatapp pre_inspection
# this is for the preview inspection changes skipable but look out is better way
def save(self):
    data = self.cleaned_data
    obj = self.pre_inspection
    print(f"the object we get for {data} and the pre inspection user {obj}")
    if data["longitude"] != "does not exist":
        obj.latitude = data['latitude']
        obj.longitude = data['longitude']
        obj.accuracy = data['accuracy']

    if data["main_gate"] != "does not exist":
        if obj.type == PreInspectionTypeEnum.SELF:
            obj.transition_pre_inspection_submit(
                link=data['main_gate'],
                description="Self Inspection: Latitude: {}, Longitude: {}, Accuracy: {}".format(
                    data['latitude'], data['longitude'], data['accuracy'])
            )
        else:
            obj.transition_pre_inspection_submit(
                link=data['main_gate'],
                by=get_current_user(),
                description="Latitude: {}, Longitude: {}, Accuracy: {}".format(
                    data['latitude'], data['longitude'], data['accuracy'])
            )
    obj.save()