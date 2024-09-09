from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from base64 import b64decode, b64encode
import json,os

APP_SECRET = os.getenv("APP_SECRET")
class FlowEndpointException(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.name = self.__class__.__name__
        self.status_code = status_code

def decrypt_request(body, private_pem, passphrase):
    encrypted_aes_key = b64decode(body['encrypted_aes_key'])
    encrypted_flow_data = b64decode(body['encrypted_flow_data'])
    initial_vector = b64decode(body['initial_vector'])

    # Load private key
    private_key = serialization.load_pem_private_key(
        private_pem.encode('utf-8'),
        password=passphrase.encode('utf-8'),
        backend=default_backend()
    )

    # Decrypt AES key
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

    # Decrypt flow data
    TAG_LENGTH = 16
    encrypted_flow_data_body = encrypted_flow_data[:-TAG_LENGTH]
    encrypted_flow_data_tag = encrypted_flow_data[-TAG_LENGTH:]

    # Decrypt the flow data using AES-128-GCM
    decipher = Cipher(
        algorithms.AES(decrypted_aes_key),
        modes.GCM(initial_vector, encrypted_flow_data_tag),
        backend=default_backend()
    ).decryptor()

    decrypted_json_string = decipher.update(encrypted_flow_data_body) + decipher.finalize()

    return {
        'decryptedBody': decrypted_json_string.decode('utf-8'),
        'aesKeyBuffer': decrypted_aes_key,
        'initialVectorBuffer': initial_vector
    }

def encrypt_response(response, aes_key_buffer, iv):
    # Flip the initialization vector
    flipped_iv = bytearray()
    for byte in iv:
        flipped_iv.append(byte ^ 0xFF)

    # Encrypt the response data
    encryptor = Cipher(algorithms.AES(aes_key_buffer),
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
