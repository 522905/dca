# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.urls import path, include
from django.views import generic
from rest_framework import routers

from . import views
from .extra_viewsets import UjjwalaApplicationExtraViewSet
from .robos.nic_error_robo import UjjwalaApplicationNicErrorRobotAPIViewSet
from .robos.robo_error_viewsets import UjjwalaApplicationRoboExecutionErrorAPIViewSet
from .robos.robo_sv_viewsets import UjjwalaApplicationSVViewSet
from .robos.sdms_relationship_robo import UjjwalaApplicationSdmsRelationshipViewSet
from .robos.sv_cancellation import SvCancellationViewSet
from .robos.viewsets import UjjwalaApplicationNicViewSet
from .views import UjjwalaApplicationWebFormView, UpdateSdmsLoginDetailsView, WebFormOldView, UjjwalaApplicationIframeWebFormView, \
    LegalDocumentsAcceptedToPendingView, ShareOnSocialMediaView, CancelInvitationView, UserDashboardView, \
    ChangeCylinderTypeRequestOverrideView
from .viewsets import UjjwalaApplicationViewSet, UjjwalaApplicationAPIViewSet, UjjwalaApplicationOtpViewSet, \
    UjjwalaPreInspectionAPIViewSet
from ujjwala.models import VaultSecret

router = routers.DefaultRouter()
router.register(r'ujjwala-application', UjjwalaApplicationViewSet)
router.register(r'ujjwala-bot', UjjwalaApplicationAPIViewSet)
router.register(r'ujjwala-preinspection', UjjwalaPreInspectionAPIViewSet, basename='ujjwala_preinspection')
router.register(r'ujjwala-nic', UjjwalaApplicationNicViewSet, basename='ujjwala_nic')
router.register(
    r'ujjwala-bot-failed-count', UjjwalaApplicationRoboExecutionErrorAPIViewSet, basename='ujjwala_bot_failed_count'
)
router.register(r'ujjwala-bot-nic-error', UjjwalaApplicationNicErrorRobotAPIViewSet)
router.register(
    r'ujjwala-bot-sdms-relationship', UjjwalaApplicationSdmsRelationshipViewSet, basename='ujjwala_sdms_relationship'
)
router.register(r'ujjwala-otp', UjjwalaApplicationOtpViewSet, basename='ujjwala_otp')
router.register(r'ujjwala-extra', UjjwalaApplicationExtraViewSet, basename='ujjwala_extra')
router.register(r'sv-cancellation', SvCancellationViewSet, basename='sv_cancellation')
router.register(r'sv-bot', UjjwalaApplicationSVViewSet, basename='sv_bot')


urlpatterns = [
    path('', views.UserDashboardView.as_view(), name='index'),
    path('', include(router.urls)),
    path('portal/web-form-old/', WebFormOldView.as_view(), name="web_form_old"),
    # path(
    #     'portal/legal_documents/upload/',
    #     generic.TemplateView.as_view(template_name="ujjwala/legal_documents_upload.html"),
    #     name="legal_documents_upload"),
    # path('portal/', generic.TemplateView.as_view(template_name="ujjwala/frontend.html"), name="index"),

    path('portal/web-form/', UjjwalaApplicationWebFormView.as_view(), name="web_form"),
 
    path('portal/i-web-form/', UjjwalaApplicationIframeWebFormView.as_view(), name="i_web_form"),
    path('portal/pre-inspection/', views.UjjwalaPreInspectionListView.as_view(), name="pre_inspection_list"),
    path('portal/web-form-share/', views.ShareWebFormLink.as_view(), name="share_web_form_link"),
    path(
        'vault-secret-autocomplete-view/',
        views.VaultSecretAutocompleteView.as_view(),
        name='vault_secret_autocomplete_view',
    ),
    path('update-sdms-login-details/', UpdateSdmsLoginDetailsView.as_view(), name='update_sdms_login_details'),
    url(
        '^portal/self-pre-inspection-share/(?P<pk>[^/.]+)/$',
        views.ShareSelfPreInspectionLink.as_view(),
        name="share_self_pre_inspection_link"
    ),
    url(
        '^portal/self-pre-inspection-share-view/(?P<data>[^/.]+)/$',
        views.SharedSelfPreInspectionLinkView.as_view(),
        name="shared_self_pre_inspection_link_view"
    ),
    # path(
    #     'portal/pre-inspection/user_list/',
    #     views.UjjwalaPreInspectionUserListView.as_view(),
    #     name="ujjwala_pre_inspection_user_listview"
    # ),
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
    # path(
    #     'portal/disbursement/first_cylinder_delivery_list/',
    #     views.FirstCylinderMaterialDeliveryListView.as_view(),
    #     name="first_cylinder_delivery_list"
    # ),
    #
    # path(
    #     'portal/disbursement/second_cylinder_delivery_list/',
    #     views.SecondCylinderMaterialDeliveryListView.as_view(),
    #     name="second_cylinder_delivery_list"
    # ),
    path(
        'portal/disbursement/list/',
        views.UjjwalaConnectionDisbursementListView.as_view(),
        name="connection_disbursement_list"
    ),

    path('portal/review_address_list/',
         views.UjjwalaAddressReviewListView.as_view(),
         name="address_review_list"
    ),

    # path('portal/pre-inspection/pre_inspection_review_list/',
    #      views.PreInspectionReviewListView.as_view(),
    #      name="pre_inspection_review_list"
    # ),

    path('portal/disbursement/review_form_abc/',
         views.ConnectionDisbursementReviewFormAbcListView.as_view(),
         name="connection_disbursement_review_form_abc_list"
    ),

    path('portal/review/review_form_abc/',
         views.ReviewFormAbcListView.as_view(),
         name="review_form_abc_list"
    ),

    path('portal/installation/installation_review_list/',
         views.InstallationReviewListView.as_view(),
         name="installation_review_list"
    ),

    path('portal/installation/installation_review_list/',
         views.InstallationReviewListView.as_view(),
         name="eighteen_above_aadaar"
    ),



    path('portal/print_documents/',
         views.PrintDocumentsView.as_view(),
         name="print_documents"
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
        '^portal/ujjwala_customer_profile/(?P<pk>[^/.]+)/$',
        views.UjjwalaApplicationCustomerProfileView.as_view(),
        name="ujjwala_customer_profile"
    ),

    url(
        '^portal/ujjwala-customer-profile-public/(?P<pk>[^/.]+)/$',
        views.UjjwalaApplicationCustomerProfilePublicView.as_view(),
        name="ujjwala_customer_profile_public"
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
        '^portal/recreate_legal_document/(?P<pk>[^/.]+)/$',
        views.RecreateLegalDocumentView.as_view(),
        name="recreate_legal_document"
    ),

    url(
        '^portal/reset_robo_failed_count/(?P<pk>[^/.]+)/$',
        views.ResetRoboFailedCount.as_view(),
        name="reset_robo_failed_count"
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

    path('portal/review/audit_application/',
         views.UjjwalaApplicationAuditListView.as_view(),
         name="ujjwala_application_audit_list"
    ),

    url(
        '^portal/ujjwala-audit-application/(?P<pk>[^/.]+)/$',
        views.UjjwalaApplicationAuditView.as_view(),
        name="ujjwala_application_audit"
    ),

    
    path('portal/change-cylinder-type/list_view/',
         views.ChangeCylinderTypeRequestListView.as_view(),
         name="change_cylinder_request_list"
    ),

    url(
        '^portal/change-cylinder-type/request/(?P<pk>[^/.]+)/$',
        views.ChangeCylinderTypeRequestView.as_view(),
        name="change_cylinder_type_request"
    ),


    path('portal/service_request/list_view/',
         views.UjjwalaApplicationServiceRequestListView.as_view(),
         name="service_request_list"
    ),

    url(
        '^portal/service-request-view/(?P<pk>[^/.]+)/$',
        views.UjjwalaApplicationServiceRequestView.as_view(),
        name="service_request_view"
    ),

    path('portal/review/bank_details_update/',
         views.BankDetailsUpdateRequestListView.as_view(),
         name="bank_details_update_list"
    ),

    url(
        '^portal/bank-details-update-request/(?P<pk>[^/.]+)/$',
        views.BankDetailsUpdateRequestView.as_view(),
        name="bank_details_update_request_view"
    ),

    url(
        '^portal/pre-inspection/(?P<type>(self|mech))/(?P<pk>[^/.]+)/$',
        views.PreInspectionView.as_view(),
        name="pre_inspection_form_view"
    ),

    # url(
    #     '^portal/pre-inspection-review/(?P<pk>[^/.]+)/$',
    #     views.PreInspectionReviewView.as_view(),
    #     name="pre_inspection_review"
    # ),

    url(
        '^portal/address-review/(?P<pk>[^/.]+)/$',
        views.UjjwalaAddressReviewView.as_view(),
        name="address_review"
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
        '^portal/update_relationship_number/(?P<pk>[^/.]+)/$',
        views.UpdateRelationshipNumberView.as_view(),
        name="update_relationship_number"
    ),
    url(
        '^portal/nic_error_update_address/(?P<pk>[^/.]+)/$',
        views.NicErrorUpdateAddress.as_view(),
        name="nic_error_update_address"
    ),
    url(
        '^portal/update_address/(?P<pk>[^/.]+)/$',
        views.UpdateAddressView.as_view(),
        name="update_address_view"
    ),
    url(
        '^portal/change_address/(?P<pk>[^/.]+)/$',
        views.ChangeAddressView.as_view(),
        name="change_address_view"
    ),
    url(
        '^portal/camunda_change_address/(?P<message_source>(STAFF|APPLICANT))/(?P<process_instance_id>[^/.]+)/(?P<agent>[^/.]+)/$',
        views.CamundaChangeAddressView.as_view(),
        name="camunda_change_address_view"
    ),
    url(
        '^portal/update_address_service_request/(?P<pk>[^/.]+)/$',
        views.UpdateAddressServiceRequestView.as_view(),
        name="update_address_service_request"
    ),
    url(
        '^portal/change_phone_number/(?P<pk>[^/.]+)/$',
        views.ChangePhoneNumberView.as_view(),
        name="change_phone_number"
    ),
    url(
        '^portal/change_cylinder_type/(?P<pk>[^/.]+)/$',
        views.ChangeCylinderTypeView.as_view(),
        name="change_cylinder_type"
    ),
    url(
        '^portal/download_change_cylinder_type_form/(?P<pk>[^/.]+)/$',
        views.DownloadChangeCylinderTypeFormView.as_view(),
        name="download_change_cylinder_type_form"
    ),
    url(
        '^portal/upload_uid_for_kyc/(?P<pk>[^/.]+)/$',
        views.UploadUIDForEKYCView.as_view(),
        name="upload_uid_for_kyc"
    ),
    url(
        '^portal/update_bank_details/(?P<pk>[^/.]+)/$',
        views.UpdateBankDetailsFormView.as_view(),
        name="update_bank_details"
    ),
    url(
        '^portal/update_bank_details_new/(?P<pk>[^/.]+)/$',
        views.UpdateBankDetailsNewFormView.as_view(),
        name="update_bank_details_new"
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
        '^portal/review/(?P<pk>[^/.]+)/review_form_abc/$',
        views.ReviewFormAbcView.as_view(),
        name="review_form_abc_view"
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
    # url(
    #     '^portal/disbursement/(?P<pk>[^/.]+)/first_cylinder_delivery_view/$',
    #     views.FirstCylinderMaterialDeliveryView.as_view(),
    #     name="first_cylinder_delivery_view"
    # ),
    # url(
    #     '^portal/disbursement/(?P<pk>[^/.]+)/second_cylinder_delivery_view/$',
    #     views.SecondCylinderMaterialDeliveryView.as_view(),
    #     name="second_cylinder_delivery_view"
    # ),
    url(
        '^portal/installation/(?P<pk>[^/.]+)/installation_review/$',
        views.InstallationReviewView.as_view(),
        name="installation_review"
    ),
    url(
        '^portal/disbursement/(?P<pk>[^/.]+)/$',
        views.ConnectionDisbursementView.as_view(),
        name="connection_disbursement_form_view"
    ),
    url(
        '^portal/nic-customer-remarks/(?P<pk>[^/.]+)/$',
        views.NicClearedCustomerRemarks.as_view(),
        name="nic_cleared_customer_remarks"
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
    url(
        '^ujjwala-application/(?P<pk>[^/.]+)/legal_documents_pending$',
        LegalDocumentsAcceptedToPendingView.as_view(),
        name="legal_documents_pending"
    ),
    url(
        '^ujjwala-application/(?P<pk>[^/.]+)/get_ekyc_status_from_sdms$',
        views.GetEKYCStatusFromSDMS.as_view(),
        name="get_ekyc_status_from_sdms"
    ),
    url(
        '^ujjwala-application/share_on_social_media/(?P<pk>[^/.]+)/$',
        ShareOnSocialMediaView.as_view(),
        name="share_on_social_media"
    ),
    url(
        '^ujjwala-application/change_cylinder_type_request/(?P<pk>[^/.]+)/override$',
        ChangeCylinderTypeRequestOverrideView.as_view(),
        name="change_cylinder_type_request_override"
    ),
    path(
        'portal/cancel_invitaion/',
        CancelInvitationView.as_view(),
        name="cancel_invitation"
    ),
    path(
        'portal/user_dashboard/',
        UserDashboardView.as_view(),
        name="user_dashboard"
    ),
    path(
        'main-menu-grid-menu-view/',
        views.MainMenuGridMenuView.as_view(),
        name="main_menu_grid_menu_view"
    ),
    path(
        'pre-inspection-grid-menu-view/',
        views.PreInspectionGridMenuView.as_view(),
        name="pre_inspection_grid_menu_view"
    ),
    path(
        'installation-grid-menu-view/',
        views.InstallationGridMenuView.as_view(),
        name="installation_grid_menu_view"
    ),
    path(
        'disbursement-grid-menu-view/',
        views.DisbursementGridMenuView.as_view(),
        name="disbursement_grid_menu_view"
    ),
    path(
        'review-grid-menu-view/',
        views.ReviewGridMenuView.as_view(),
        name="review_grid_menu_view"
    ),
    path(
        'print-command-menu-view/',
        views.NewBarCodeLabelPrintView.as_view(),
        name="print_command_menu_view"
    ),
]
