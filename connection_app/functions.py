
def can_do_post_inspection(user):
	return user.has_perm('connection_app.can_do_post_inspection')


def get_delivery_boy_login(customer_profile_id):
	from connection_app.models import CustomerProfile
	from teams.models import SDMSServiceArea, UserProfile

	cp_obj = CustomerProfile.objects.get(id=customer_profile_id)
	userprofile_obj: UserProfile = cp_obj.sdms_service_area.userprofile_set.first()

	return userprofile_obj.sdmsuser_set.filter(distributor=cp_obj.distributor).first().delivery_boy_login
