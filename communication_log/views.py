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

from communication_log.flow_encryption import decrypt_request
from communication_log.jobs import interakt_webhook_job_processing, infobip_webhook_job_processing, \
    interakt_flow_template
from ujjwala.views import WhatsappPreInspection
from ujjwala.views import check_ujwaala_status


@csrf_exempt
def interakt_webhook(request, is_async=True):
    logging.info(request.body)
    data = json.loads(request.body)
    # django_rq.enqueue(interakt_webhook_job_processing, args=(data,), is_async=is_async)
    interakt_webhook_job_processing(data)
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

            phone_no = decrypted_body.get('messages', {}).get('context', {}).get('from', " ") or " "
            print("💬 Decrypted Request:", decrypted_body)
            # Example Flow Token Validation (Uncomment and implement your logic)
            # if not is_valid_flow_token(decrypted_body.get('flow_token')):
            #     error_response = {'error_msg': 'The message is no longer available'}
            #     encrypted_response = encrypt_response(error_response, aes_key_buffer, initial_vector_buffer)
            #     return HttpResponse(encrypted_response, status=427, content_type='application/json')
            if decrypted_body.get('action') == 'ping':
                response = {"data": {"status": "active"}}
            else:
                response = {
                               "screen": "SUCCESS",
                               "data": {
                                   "extension_message_response": {
                                       "params": {
                                           "flow_token": decrypted_body.get('flow_token') or "test request ",
                                           "some_param_name": "PASS_CUSTOM_VALUE"
                                       }
                                   }
                               }
                           }
                WhatsappPreInspection(Inspection_data=decrypted_body.data, unique_id=phone_no, intent="address_details")

            print("👉 Response to Encrypt:", response)
            # encrypted_response = encrypt_response(response, aes_key_buffer, initial_vector_buffer)
            return HttpResponse(encrypt_response(response, aes_key_buffer, initial_vector_buffer), content_type='text/plain')
            # return HttpResponse(encrypted_response, content_type='application/json', status= 200)
        except FlowEndpointException as e:
            return HttpResponse(status=e.status_code)
        except Exception as e:
            print(e)
            return HttpResponse(status=500)
    return HttpResponse('<pre>Nothing to see here.\nCheckout README.md to start.</pre>')


def decrypt_request(body, private_pem, passphrase):
    encrypted_aes_key = b64decode(body['encrypted_aes_key'])
    encrypted_flow_data = b64decode(body['encrypted_flow_data'])
    initial_vector = b64decode(body['initial_vector'])

    private_key = load_pem_private_key(private_pem.encode('utf-8'), password=passphrase.encode('utf-8'),
                                       backend=default_backend())

    try:
        decrypted_aes_key = private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
    except Exception as error:
        print(error)
        raise FlowEndpointException(421, "Failed to decrypt the request. Please verify your private key.")

    TAG_LENGTH = 16
    encrypted_flow_data_body = encrypted_flow_data[:-TAG_LENGTH]
    encrypted_flow_data_tag = encrypted_flow_data[-TAG_LENGTH:]

    decipher = Cipher(
        algorithms.AES(decrypted_aes_key),
        modes.GCM(initial_vector, encrypted_flow_data_tag),
        backend=default_backend()
    ).decryptor()

    decrypted_json_string = decipher.update(encrypted_flow_data_body) + decipher.finalize()
    return {
        'decryptedBody': json.loads(decrypted_json_string.decode('utf-8')),
        'aesKeyBuffer': decrypted_aes_key,
        'initialVectorBuffer': initial_vector
    }


def encrypt_response(response, aes_key, iv):
    # Flip the initialization vector
    flipped_iv = bytearray()
    for byte in iv:
        flipped_iv.append(byte ^ 0xFF)

    # Encrypt the response data
    encryptor = Cipher(algorithms.AES(aes_key),
                       modes.GCM(flipped_iv)).encryptor()
    return b64encode(
        encryptor.update(json.dumps(response).encode("utf-8")) +
        encryptor.finalize() +
        encryptor.tag
    ).decode("utf-8")


def is_request_signature_valid(request):
    if not APP_SECRET:
        print("App Secret is not set up. Please add your app secret in the environment to check for request validation")
        return True

    signature_header = request.headers.get('x-hub-signature-256')
    if not signature_header:
        print("Missing signature header.")
        return False

    signature_buffer = bytes.fromhex(signature_header.replace("sha256=", ""))
    hmac_instance = hmac.HMAC(APP_SECRET.encode('utf-8'), hashes.SHA256(), backend=default_backend())
    hmac_instance.update(request.body)
    digest_buffer = hmac_instance.finalize()

    if not hmac.compare_digest(digest_buffer, signature_buffer):
        print("Error: Request signature did not match")
        return False
    return True


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

            elif intent_name == 'aaddress.details-main-gate-pin-location':
                response_texts = WhatsappPreInspection(Inspection_data=user_input, unique_id=session_id, intent="pin-location")
                print(f'the response text by pin-location data : {response_texts}')

            elif intent_name == 'address.details - main-gate':
                response_texts = WhatsappPreInspection(Inspection_data=user_input, unique_id=session_id, intent="main-gate")

            elif intent_name == 'address.details-pin-location-kitchen':
                response_texts = WhatsappPreInspection(Inspection_data=user_input, unique_id=session_id, intent="kitchen-photo")
                interakt_flow_template(session_id)

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
