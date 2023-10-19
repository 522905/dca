from config import settings
from frappeclient.frappeclient import FrappeClient


def get_old_erp_client():
	erp_client = FrappeClient("https://erp.arungas.com")  # Production Env

	return erp_client


def get_new_erp_client():
	# erp_client = FrappeClient("https://erp.arunlogistics.com")  # Production Env
	# erp_client.authenticate("af54f14c96f4a44", "b1d68927a464220")  # Production Env
	#
	# # client = FrappeClient("http://mysite.localhost:33322")  # Test Env Docker At 192.168.1.77
	# # client.authenticate("488d472c9926909", "27006b9fc7cfae8")  # Test Env Docker At 192.168.1.77
	# return erp_client

	erp_client = FrappeClient(settings.ERP_SERVER_URL)  # Production Env
	erp_client.authenticate(settings.ERP_API_KEY, settings.ERP_API_SECRET)  # Production Env
	return erp_client


old_erp_client = get_old_erp_client()
new_erp_client = get_new_erp_client()
