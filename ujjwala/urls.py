# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.contrib.auth.decorators import permission_required
from django.urls import path, include
from django.contrib import admin
from email.mime import application

from django.views import generic
from django.views.generic import TemplateView
from rest_framework import routers

from connection_app.viewsets import ConnectionApplicationViewSet

from . import views
from .robos.nic_error_robo import UjjwalaApplicationNicErrorRobotAPIViewSet
from .robos.sdms_relationship_robo import UjjwalaApplicationSdmsRelationshipViewSet
from .views import UjjwalaApplicationWebFormView, WebFormOldView, UjjwalaApplicationIframeWebFormView
from .viewsets import UjjwalaApplicationViewSet, UjjwalaApplicationAPIViewSet, UjjwalaApplicationOtpViewSet

router = routers.DefaultRouter()
router.register(r'ujjwala-application', UjjwalaApplicationViewSet)
router.register(r'ujjwala-bot', UjjwalaApplicationAPIViewSet)
router.register(r'ujjwala-bot-nic-error', UjjwalaApplicationNicErrorRobotAPIViewSet)
router.register(
    r'ujjwala-bot-sdms-relationship', UjjwalaApplicationSdmsRelationshipViewSet, basename='ujjwala_sdms_relationship'
)
router.register(r'ujjwala-otp', UjjwalaApplicationOtpViewSet, basename='ujjwala_otp')

urlpatterns = [
    path('', views.index),
    path('', include(router.urls)),
    path('portal/web-form-old/', WebFormOldView.as_view(), name="web_form_old"),
    # path(
    #     'portal/legal_documents/upload/',
    #     generic.TemplateView.as_view(template_name="ujjwala/legal_documents_upload.html"),
    #     name="legal_documents_upload"),
    # path('portal/', generic.TemplateView.as_view(template_name="ujjwala/frontend.html"), name="index"),

    path('portal/web-form/', UjjwalaApplicationWebFormView.as_view(), name="web_form"),
    path('portal/i-web-form/', UjjwalaApplicationIframeWebFormView.as_view(), name="i_web_form"),
    path('portal/pre-inspection/', views.UjjwalaPreInspectionListView.as_view(), name="index"),
    path('portal/web-form-share/', views.ShareWebFormLink.as_view(), name="share_web_form_link"),

    path(
        'portal/disbursement/sv_label_print/',
        views.UjjwalaConnectionDisbursementSvLabelPrintListView.as_view(),
        name="connection_disbursement_sv_label_print_list"
    ),

    path(
        'portal/disbursement/social_media_updates/',
        views.UjjwalaConnectionDisbursementSocialMediaUpdatesListView.as_view(),
        name="connection_disbursement_social_media_updates_list"
    ),
    path(
        'portal/disbursement/material_delivery/',
        views.UjjwalaConnectionDisbursementMaterialDeliveryListView.as_view(),
        name="connection_disbursement_material_delivery_list"
    ),

    path(
        'portal/disbursement/list/',
        views.UjjwalaConnectionDisbursementListView.as_view(),
        name="connection_disbursement_list"
    ),

    path('portal/disbursement/review_form_abc/',
         views.ConnectionDisbursementReviewFormAbcListView.as_view(),
         name="connection_disbursement_review_form_abc_list"
    ),

    path(
        'portal/pre-inspection/create/',
        views.PreInspectionCreateView.as_view(),
        name="pre_inspection_create"
    ),

    url(
        '^ujjwala-otp/display_otp/(?P<ref_no>[^/.]+)/$',
        views.UjjwalaApplicationDisplayOtp.as_view(),
        name="ujjwala_application_display_otp"
    ),

    url(
        '^portal/ujjwala_application_link/(?P<data>[^/.]+)/$',
        views.UjjwalaApplicationSharedLinkView.as_view(),
        name="ujjwala_application_link"
    ),

    url(
        '^portal/whatsapp_nic_error_update_address/(?P<pk>[^/.]+)/$',
        views.WhatsappNicErrorUpdateAddress.as_view(),
        name="whatsapp_nic_error_update_address"
    ),

    url(
        '^portal/whatsapp_pre_inspection_type_self/(?P<pk>[^/.]+)/$',
        views.WhatsappPreInspectionTypeSelf.as_view(),
        name="whatsapp_pre_inspection_type_self"
    ),

    url(
        '^portal/whatsapp_form_abc/(?P<pk>[^/.]+)/$',
        views.WhatsappUploadLegalForms.as_view(),
        name="whatsapp_form_abc"
    ),
    url(
        '^portal/whatsapp_update_bank_details/(?P<pk>[^/.]+)/$',
        views.WhatsappUpdateBankDetailsView.as_view(),
        name="whatsapp_update_bank_details"
    ),

    path(
        'portal/application-status-search/',
        views.UjjwalaApplicationStatusView.as_view(),
        name="application_status_search"
    ),

    url(
        '^portal/pre-inspection/(?P<type>(self|mech))/(?P<pk>[^/.]+)/$',
        views.PreInspectionView.as_view(),
        name="pre_inspection_form_view"
    ),

    url(
        '^portal/pre-inspection/convert_to/(?P<convert_to>(self|mech))/(?P<pk>[^/.]+)/$',
        views.PreInspectionConvertToView.as_view(),
        name="pre_inspection_view_convert_to"
    ),

    # url(
    #     '^portal/pre-inspection/(?P<pk>[^/.]+)/$',
    #     views.PreInspectionView.as_view(),
    #     name="pre_inspection_form_view"
    # ),

    url(
        '^portal/legal_documents_upload/(?P<pk>[^/.]+)/$',
        views.UjjwalaApplicationLegalDocumentsUpload.as_view(),
        name="legal_documents_upload"
    ),
    url(
        '^portal/set_primary_phone_number/(?P<pk>[^/.]+)/$',
        views.SetPrimaryPhoneNumberView.as_view(),
        name="set_primary_phone_number"
    ),
    url(
        '^portal/nic_error_update_address/(?P<pk>[^/.]+)/$',
        views.NicErrorUpdateAddress.as_view(),
        name="nic_error_update_address"
    ),
    url(
        '^portal/update_bank_details/(?P<pk>[^/.]+)/$',
        views.UpdateBankDetailsFormView.as_view(),
        name="update_bank_details"
    ),

    # url(
    #     '^portal/connection-disbursement/(?P<pk>[^/.]+)/send_invitation/$',
    #     views.SendInvitationView.as_view(),
    #     name="connection_disbursement_send_invitation_view"
    # ),

    url(
        '^portal/disbursement/(?P<pk>[^/.]+)/review_form_abc/$',
        views.ConnectionDisbursementReviewFormAbcView.as_view(),
        name="connection_disbursement_review_form_abc_view"
    ),

    url(
        '^portal/disbursement/(?P<pk>[^/.]+)/barcode_label_print/$',
        views.BarCodeLabelPrintView.as_view(),
        name="connection_disbursement_barcode_label_print_view"
    ),

    url(
        '^portal/disbursement/(?P<pk>[^/.]+)/sv_label_print/$',
        views.ConnectionDisbursementSvLabelPrintView.as_view(),
        name="connection_disbursement_sv_label_print_view"
    ),

    url(
        '^portal/disbursement/(?P<pk>[^/.]+)/social_media_updates/$',
        views.ConnectionDisbursementSocialMediaUpdatesView.as_view(),
        name="connection_disbursement_social_media_updates_view"
    ),

    url(
        '^portal/disbursement/(?P<pk>[^/.]+)/material_delivery/$',
        views.ConnectionDisbursementMaterialDeliveryView.as_view(),
        name="connection_disbursement_material_delivery_view"
    ),
    url(
        '^portal/disbursement/(?P<pk>[^/.]+)/$',
        views.ConnectionDisbursementView.as_view(),
        name="connection_disbursement_form_view"
    ),

    url(
        '^portal/pre-inspection/(?P<pk>[^/.]+)/$',
        views.PreInspectionView.as_view(),
        name="pre_inspection_form_view"
    ),

    url(
        '^ujjwala-application/(?P<pk>[^/.]+)/status/$',
        views.ApplicationStatusView.as_view(),
        name="application_status"
    ),

    path(
         'portal/disbursement_photo_upload/', generic.TemplateView.as_view(
            template_name="ujjwala/disbursement/disbursement_photo_upload.html"
         ), name="disbursement_photo_upload"
     ),

     path('portal/installation/', views.InstallationListView.as_view(), name="installation_list"),
     
     url(
        '^portal/installation/(?P<pk>[^/.]+)/$',
        views.InstallationView.as_view(),
        name="installation_form_view"
    ),
]
