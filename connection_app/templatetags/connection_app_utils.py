from django import template

from connection_app.functions import can_do_post_inspection

register = template.Library()


@register.filter()
def has_post_inspection_permission(user):
	return can_do_post_inspection(user)
