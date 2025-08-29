import requests


class ZohoCatalyst(object):

	def __init__(self, client_id, client_secret, project_id):
		self.client_id = client_id
		self.client_secret = client_secret
		self.project_id = project_id

		self.refresh_token = ''
		self.access_token = ''

	def create_refresh_token(self, grant_code):
		"""
		{
			"access_token": "1000.6c7364d8562dd85a902b5f634dae2aba.876aa02b52bd9d7838805ae558b31875",
			"refresh_token": "1000.d2b6cf3bcd1bc0b081da19c3ff4bd71f.9e97085a4e407204fb2e98eaa3986bd9",
			"api_domain": "https://www.zohoapis.com",
			"token_type": "Bearer",
			"expires_in": 3600
		}
		"""

		resp = requests.post(
			"https://accounts.zoho.in/oauth/v2/token",
			params={
				'grant_type': 'authorization_code',
				'code': grant_code,
				'client_id': self.client_id,
				'client_secret': self.client_secret,
				'redirect_uri': 'www.zoho.com'
			}
		)
		print(resp.text)

		resp = resp.json()

		self.refresh_token = resp.get('refresh_token')
		self.access_token = resp.get('access_token')

	def refresh_access_token(self):
		"""
		{
			"access_token":"1000.48e4b0686148ab2d0831debfddc86aea.e60bea0b4a08ae2d0320a6488ed99603",
			"api_domain":"https://www.zohoapis.com",
			"token_type":"Bearer",
			"expires_in":3600
		}
		"""

		resp = requests.post(
			"https://accounts.zoho.com/oauth/v2/token",
			params={
				'grant_type': 'refresh_token',
				'refresh_token': self.refresh_token,
				'client_id': self.client_id,
				'client_secret': self.client_secret,
				'redirect_uri': 'www.zoho.com'
			}).json()

		self.access_token = resp.get('access_token')

		print(f'Access Token: {self.access_token}')

	def get_details_from_aadhaar(self, uid_front_url, uid_back_url):
		'https://api.catalyst.zoho.com/baas/v1/project/12429000000003010/ml/ocr'
		{'status': 'failure', 'data': {'error_code': 'INVALID_TOKEN', 'message': 'invalid oauth token'}}
		"""
		{
			"pincode": "141008",
			"address": {
				"prob": 0.5,
				"value": "D/O Raj Kumar, House No.2204, Street No. 5/2 Ward 9, Near Parkash Karyana Store, Adarsh Nagar,ludhiana, Ludhiana, Punjab -141008"
			},
			"gender": {
				"prob": 0.8,
				"value": "FEMALE"
			},
			"dob": {
				"prob": 0.8,
				"value": "24/05/1998"
			},
			"name": {
				"prob": 0.5,
				"value": "Pooja Rani"
			},
			"aadhaar": {
				"prob": 0.8,
				"value": "409233274134"
			}
		}
		"""

		uid_front_file = requests.get(uid_front_url)
		uid_back_file = requests.get(uid_back_url)

		resp = requests.post(
			f'https://api.catalyst.zoho.in/baas/v1/project/{self.project_id}/ml/ocr',
			headers={
				'Authorization': f'Zoho-oauthtoken {self.access_token}'
			},
			data={
				'model_type': 'AADHAAR',
				'language': 'eng'
			},
			files={
				'aadhaar_front': ('uid_f.jpeg', uid_front_file.content),
				'aadhaar_back': ('uid_b.jpeg', uid_back_file.content)
			}
		)

		resp = resp.json()

		if resp.get('status') == 'failure' and resp.get('data').get('error_code') == 'INVALID_TOKEN':
			self.refresh_access_token()
			return self.get_details_from_aadhaar(uid_front_url, uid_back_url)

		return resp


CLIENT_ID = '1000.EAW6IW9F9TZDS7VXWLDJ3Q1XQBBTUO'
CLIENT_SECRET = '6ea5fb7c5c8a43a3294733ffa9808280a72593e8cd'
PROJECT_ID = '17193000000010109'
zoho_client = ZohoCatalyst(CLIENT_ID, CLIENT_SECRET, PROJECT_ID)
zoho_client.refresh_token = '1000.37ce5369c9a188442862da639ed322e2.1b31814496396f4162eef792c2fef30c'
zoho_client.access_token = '1000.2ca66ad5ae733b4ec15ab2ee2d9e02c4.b1553434f15ce31260d083eefc00eb0b'

# if __name__ == '__main__':

# 	CLIENT_ID = '1000.EAW6IW9F9TZDS7VXWLDJ3Q1XQBBTUO'
# 	CLIENT_SECRET = '6ea5fb7c5c8a43a3294733ffa9808280a72593e8cd'
# 	PROJECT_ID = '17193000000010109'


# 	grant_code = '1000.74812b19bf6f769121cd47bf5bba2dfe.663ba7861863dc78313ba9bd5c8b07a3'
# 	zoho_client.create_refresh_token(grant_code)

# 	uid_ocr = zc.get_details_from_aadhaar(
# 		'http://dca.arungas.com:6988/unsafe/filters:format(jpeg)/https://tus.dca.arungas.com/files/f77d002dcf3b284fba090264a31c007e',
# 		'http://dca.arungas.com:6988/unsafe/filters:format(jpeg)/https://tus.dca.arungas.com/files/4096a8a0efba9a075e03161e355afeb9'
# 	)

# 	# # zc.get_refresh_token_from_grant_code(grant_code)
# 	#
# 	#
# 	# print(uid_ocr)