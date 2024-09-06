from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

class FlowEndpointException(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.name = self.__class__.__name__
        self.status_code = status_code

def decrypt_request(body, private_pem, passphrase):
    encrypted_aes_key = base64.b64decode(body['encrypted_aes_key'])
    encrypted_flow_data = base64.b64decode(body['encrypted_flow_data'])
    initial_vector = base64.b64decode(body['initial_vector'])

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

def encrypt_response(response, aes_key_buffer, initial_vector_buffer):
    # Flip initial vector
    flipped_iv = bytes([~b & 0xFF for b in initial_vector_buffer])

    # Encrypt response data using AES-128-GCM
    cipher = Cipher(
        algorithms.AES(aes_key_buffer),
        modes.GCM(flipped_iv),
        backend=default_backend()
    ).encryptor()

    encrypted_response = cipher.update(response.encode('utf-8')) + cipher.finalize()
    return base64.b64encode(encrypted_response + cipher.tag).decode('utf-8')
