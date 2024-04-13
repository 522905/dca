
def can_do_post_inspection(user):
	return user.has_perm('connection_app.can_do_post_inspection')
