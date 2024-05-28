from django import template

from connection_app.functions import can_do_post_inspection

register = template.Library()


@register.filter()
def has_post_inspection_permission(user):
	return can_do_post_inspection(user)


@register.filter()
def query_filter(value, attr):
	return value.filter(**eval(attr))


@register.filter
def get(mapping, key):
	return mapping.get(key, '')
