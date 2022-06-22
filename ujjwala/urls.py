# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.urls import path, include
from django.contrib import admin
from email.mime import application

from django.views import generic
from rest_framework import routers

from connection_app.viewsets import ConnectionApplicationViewSet

from . import views
from . import views
from .viewsets import UjjwalaApplicationViewSet, UjjwalaApplicationAPIViewSet

router = routers.DefaultRouter()
router.register(r'ujjwala-application', UjjwalaApplicationViewSet)
router.register(r'ujjwala-bot', UjjwalaApplicationAPIViewSet)

urlpatterns = [
    path('', views.index),
    path('', include(router.urls)),
    # path(
    #     'portal/legal_documents/upload/',
    #     generic.TemplateView.as_view(template_name="ujjwala/legal_documents_upload.html"),
    #     name="legal_documents_upload"),
    # path('portal/', generic.TemplateView.as_view(template_name="ujjwala/frontend.html"), name="index"),

    path('portal/pre-inspection/', views.UjjwalaPreInspectionListView.as_view(), name="index"),

    path(
        'portal/connection-disbursement/',
        views.UjjwalaConnectionDisbursementListView.as_view(),
        name="connection_disbursement_list"
    ),

    path('portal/pre-inspection/review/', views.PreInspectionReviewView.as_view(), name="review"),

    path(
        'portal/pre-inspection/create/',
        views.PreInspectionCreateView.as_view(),
        name="pre_inspection_create"
    ),

    url(
        '^portal/pre-inspection/(?P<pk>[^/.]+)/$',
        views.PreInspectionView.as_view(),
        name="pre_inspection_form_view"
    ),
    
    url(
        '^portal/legal_documents_upload/(?P<pk>[^/.]+)/$',
        views.UjjwalaApplicationLegalDocumentsUpload.as_view(),
        name="legal_documents_upload"
    ),

    url(
        '^portal/connection-disbursement/(?P<pk>[^/.]+)/$',
        views.ConnectionDisbursementView.as_view(),
        name="connection_disbursement_form_view"
    ),
    # url(
    #     '^portal/disbursement_photo_upload/(?P<pk>[^/.]+)/$',
    #     views.ConnectionDisbursementMaterialDeliveryView.as_view(),
    #     name="disbursement_photo_upload"
    # ),

    # url(
    #     '^pre_inspection_allocated/(?P<pk>[^/.]+)/$',
    #     PreInspectionAllocatedOtpView.as_view(),
    #     name="pre_inspection_allocated"
    # ),

    url(
        '^ujjwala-application/(?P<pk>[^/.]+)/reupload/$',
        views.UjjwalaApplicationReuploadView.as_view(),
        name="application_reupload"
    ),
    url(
        '^ujjwala-application/(?P<pk>[^/.]+)/status/$',
        views.ApplicationStatusView.as_view(),
        name="application_status"
    ),

    # Deprecated Create URL
    # path(
    #     'portal/pre-inspection/deprecated-create/', generic.TemplateView.as_view(
    #         template_name="ujjwala/pre_inspection_search.html"
    #     ), name="pre_inspection_search"
    # ),

     path(
         'portal/disbursement_photo_upload/', generic.TemplateView.as_view(
             template_name="ujjwala/disbursement_photo_upload.html"
         ), name="disbursement_photo_upload"
     ),

     path('portal/installation/', views.InstallationListView.as_view(), name="installation_list"),
     
     url(
        '^portal/installation/(?P<pk>[^/.]+)/$',
        views.InstallationView.as_view(),
        name="installation_form_view"
    ),

]
