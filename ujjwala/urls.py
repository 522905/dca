# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.urls import path, include
from django.contrib import admin
from email.mime import application

from django.views import generic
from rest_framework import routers

from connection_app.viewsets import ConnectionApplicationViewSet

from . import views
from .forms import PreInspectionWizardForm
from .viewsets import UjjwalaApplicationViewSet, UjjwalaApplicationAPIViewSet

router = routers.DefaultRouter()
router.register(r'ujjwala-application', UjjwalaApplicationViewSet)
router.register(r'ujjwala-bot', UjjwalaApplicationAPIViewSet)

urlpatterns = [
    path('', views.index),
    path('', include(router.urls)),
    path('frontend/', generic.TemplateView.as_view(template_name="ujjwala/frontend.html"), name="index"),
    url(
        '^pre_inspection/(?P<pk>[^/.]+)/$',
        PreInspectionWizardForm.as_view(),
        name="pre_inspection_detail_view"
    ),
    # path('pre_inspection_listview/', views.UjjwalaPreInspectionListView.as_view(), name="pre_inspection_listview"),
    path(
        'pre_inspection_search/', generic.TemplateView.as_view(
            template_name="ujjwala/pre_inspection_search.html"
        ), name="pre_inspection_search"),
    url(
        '^ujjwala-application/(?P<pk>[^/.]+)/reupload/$',
        views.UjjwalaApplicationReuploadView.as_view(),
        name="application_reupload"
    )
]
