import hvac
import sys

# Authentication
from domestic_app import settings

client: hvac.Client = hvac.Client(
    url='http://vault.arungas.com',
    token=settings.HASHICORP_VAULT_TOKEN,
)


# # Writing a secret
# create_response = client.secrets.kv.v2.create_or_update_secret(
#     path='my-secret-password',
#     secret=dict(password='Hashi123'),
# )
#
# print('Secret written successfully.')
#
# # Reading a secret
# read_response = client.secrets.kv.read_secret_version(path='my-secret-password')
#
# password = read_response['data']['data']['password']
#
# if password != 'Hashi123':
#     sys.exit('unexpected password')
#
# print('Access granted!')

