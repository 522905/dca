from django import template

register = template.Library()


@register.filter(name='banner_content')
def banner_content(banners_list, name):
    if type(banners_list) != str:
        banner = banners_list.filter(name=name).first()
        if banner:
            return banner.content
