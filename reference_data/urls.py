from django.conf.urls import url
from django.urls import path

from reference_data import views

urlpatterns = [
	url(
        '^html-template/(?P<data>[^/.]+)/$',
		views.HTMLTemplateView.as_view(), name="html_template_view"
	)
]
