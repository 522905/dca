import json
import logging
import os
import re
from base64 import b64decode, b64encode

import django_rq
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from communication_log.flow_Encryption import decrypt_request,encrypt_response
from communication_log.jobs import interakt_webhook_job_processing, infobip_webhook_job_processing, \
    interakt_flow_template
from ujjwala.views import WhatsappPreInspection
from ujjwala.views import check_ujwaala_status


@csrf_exempt
def interakt_webhook(request, is_async=True):
    logging.info(request.body)
    data = json.loads(request.body)
    django_rq.enqueue(interakt_webhook_job_processing, args=(data,), is_async=is_async)
    # interakt_webhook_job_processing(data)
    return HttpResponse(status=200)


@csrf_exempt
def infobip_webhook(request, is_async=True):
    data = json.loads(request.body)
    django_rq.enqueue(infobip_webhook_job_processing, args=(data,), is_async=is_async)
    return HttpResponse(status=200)

logger = logging.getLogger(__name__)
# Simulate a persistent store
APP_SECRET = os.getenv("APP_SECRET")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PASSPHRASE = os.getenv("PASSPHRASE", "")


class FlowEndpointException(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.name = self.__class__.__name__
        self.status_code = status_code


@csrf_exempt
def flowhook(request):
    if request.method == 'POST':
        print(f"this webhook host request contain this data {request}")

        if not PRIVATE_KEY:
            return HttpResponse('Private key is empty. Please check your env variable "PRIVATE_KEY".', status=500)

        # if not is_request_signature_valid(request):
        #     return HttpResponse(status=432)


        try:
            decrypted_request = decrypt_request(json.loads(request.body), PRIVATE_KEY, PASSPHRASE)
            aes_key_buffer = decrypted_request['aesKeyBuffer']
            initial_vector_buffer = decrypted_request['initialVectorBuffer']
            decrypted_body = decrypted_request['decryptedBody']
            print(f"the type of variable decrypt_body is : {type(decrypted_body)}")
            if isinstance(decrypted_body, str):
                try:
                    decrypted_body = json.loads(decrypted_body)
                except json.JSONDecodeError:
                    raise ValueError("decryptedBody is not valid JSON")

            # Now safely access 'data' within the decrypted_body dictionary
            decrypted_data = decrypted_body.get('data', None)

            if decrypted_data is None:
                raise KeyError("Key 'data' not found in decryptedBody")

            logger.info(f"the decrypted request contain: {decrypted_request} from {request}")
            phone_no = decrypted_body.get('messages', {}).get('context', {}).get('from', " ") or " "
            print("💬 Decrypted Request:", decrypted_body, decrypted_data , )
            if decrypted_body.get('action') == 'ping':
                response = {"data": {"status": "active"}}
            else:
                response = {
                               "screen": "SUCCESS",
                               "data": {
                                   "extension_message_response": {
                                       "params": {
                                           "flow_token": decrypted_body.get('flow_token') or "test request ",
                                           "data": decrypted_data or "some issue with data retrival"
                                       }
                                   }
                               }
                           }
                # WhatsappPreInspection(Inspection_data=decrypted_data, unique_id=phone_no, intent="address_details")

            print("👉 Response to Encrypt:", response)
            # encrypted_response = encrypt_response(response, aes_key_buffer, initial_vector_buffer)
            return HttpResponse(encrypt_response(response, aes_key_buffer, initial_vector_buffer), content_type='text/plain')
            # return HttpResponse(encrypted_response, content_type='application/json', status= 200)
        except FlowEndpointException as e:
            logger.error(f"flowend point exception: {str(e)}")
            return HttpResponse(status=e.status_code)
        except Exception as e:
            print(e)
            logger.error(f"Unexpected error: {str(e)}")
            return HttpResponse(status=500)
    return HttpResponse('<pre>Nothing to see here.\nCheckout README.md to start.</pre>')


@csrf_exempt
def webhook(request):

    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            # Validate incoming data
            intent_name = data.get('queryResult', {}).get('intent', {}).get('displayName')
            user_input = data.get('queryResult', {}).get('queryText')
            session_url = data.get("session")
            if not intent_name or not user_input or not session_url:
                logger.error(f"Missing required fields in the request data. {session_url}")
                return JsonResponse({'error': 'Missing required fields.'}, status=400)

            match = re.search(r'/sessions/([^/]+)/?', session_url)
            if not match:
                logger.error("Invalid session format in the session URL.")
                return JsonResponse({'error': 'Invalid session format.'}, status=400)

            session_id = match.group(1)
            response_texts = ''
            print(session_id)

            # Handle different intents
            if intent_name == 'ujjwala.status':
                response_texts = check_ujwaala_status(session_id)

            elif intent_name == 'address.details-main-gate-pin-location':
                response_texts = WhatsappPreInspection(Inspection_data=user_input, unique_id=session_id,
                                                       intent="pin-location")
                print(f'the response text by pin-location data : {response_texts}')

            elif intent_name == 'address.details - main-gate':
                if user_input.find(".jpeg") != -1:
                    response_texts = WhatsappPreInspection(Inspection_data=user_input, unique_id=session_id,
                                                           intent="main-gate")
                else:
                    response_texts = "please only share image"
            elif intent_name == 'address.details-pin-location-kitchen':
                if user_input.find(".jpeg") != -1:
                    response_texts = WhatsappPreInspection(Inspection_data=user_input, unique_id=session_id,
                                                           intent="kitchen-photo")
                    interakt_flow_template(session_id)
                else:
                    response_texts = "please only share image"

            return JsonResponse({'fulfillmentText': response_texts})

        except json.JSONDecodeError:
            logger.error("Invalid JSON received.")
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)

        except KeyError as e:
            logger.error(f"Missing key in the data: {str(e)}")
            return JsonResponse({'error': f'Missing key: {str(e)}'}, status=400)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return JsonResponse({'error': f'An unexpected error occurred. {e}'}, status=500)

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
