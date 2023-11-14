import base64
import datetime
import textwrap

import django_rq
from dateutil.relativedelta import relativedelta
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.signing import Signer
from django.forms import formset_factory
from django.http import HttpResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django_currentuser.middleware import get_current_user

from communication_log.models import CommunicationLog
from otp.models import Otp
from ujjwala.enums import UjjwalaV2ApplicationStatus, PreInspectionStatusEnum, ConnectionDisbursementStatusEnum, \
    PreInspectionTypeEnum, DisbursementDriveStatusEnum, UjjwalaApplicationDocumentsEnum, NicClearedCustomerRemarksEnum, \
    UjjwalaV2ApplicationAvailabilityChannel, ConnectionDisbursementInvitationEnum
from ujjwala.forms import UjjwalaDocumentsReuploadForm, PreInspectionInitialForm, \
    PreInspectionGenerateOtpForm, PreInspectionValidateOtpForm, \
    KitchenPreInspectionForm, AudioOnSafetyForm, PreviewPreInspectionForm, PreInspectionAllocatedGenerateOtpForm, \
    PreInspectionAllocatedValidateOtpForm, UjjwalaLegalDocumentsUpload, ChangeAddressForm, \
    ConnectionDisbursementSvLabelPrintForm, InstallationMainGateUploadForm, InstallationKitchenUploadForm, \
    UjjwalaApplicationGenerateOtpForm, UjjwalaApplicationValidateOtpForm, \
    ConnectionDisbursementMaterialDeliveryForm, ConnectionDisbursementInvitationForm, \
    ConnectionDisbursementSocialMediaUpdatesForm, NicUpdateAddressForm, \
    PreInspectionConvertForm, LegalDocumentsReviewAdminForm, SetPrimaryPhoneNumberForm, \
    UpdateBankDetailsForm, NicClearedCustomerRemarksForm, PrintDocumentsForm, \
    InstallationReviewAdminForm, FirstCylinderMaterialDeliveryForm, SecondCylinderMaterialDeliveryForm, \
    PreInspectionReviewAdminForm, CancelInvitationForm, UpdateAddressForm, \
    NewRelationCreated
from ujjwala.global_functions import login_required_if_mech_inspection
from ujjwala.models import UjjwalaV2Application, PreInspection, ConnectionDisbursement, \
    FamilyMembers, DisbursementDrive
from ujjwala.ujjwala_functions import ujjwala_application_reject_reason_log, is_pre_inspection_applicable, \
    send_ujjwala_application_whatsapp_link_v2, download_audit_documents_for_ids, is_member_of_disbursement_drive, \
    get_current_user_disbursement_drive, is_member_of_second_cylinder_delivery, \
    send_ujjwala_self_pre_inspection_share_link, is_member_of_reviewer_group, send_ujjwala_share_on_social_media_link, \
    send_otp_using_channel
from utils.enums import RoboSdmsDedeupStatusEnum
from utils.global_functions import unsign_data_base64, sign_data_base64


def index(request):
    return redirect('ujjwala:web_form')


def legal_documents(request):
    return render(request, 'ujjwala/legal-document-upload-form.html')


@method_decorator(login_required, 'dispatch')
class WebFormOldView(View):
    def dispatch(self, request, *args, **kwargs):
        user = get_current_user()
        if user.has_perm('can_fill_old_ujjwala_form', 'ujjwala'):
            return render(request, 'ujjwala/web_form_old.html')
        else:
            return HttpResponse("You do not have permission to fill this form. Contact Admin")


# I Frame Web Form View To Display Form In Website
# With
@method_decorator(xframe_options_exempt, 'dispatch')
@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationIframeWebFormView(TemplateView):
    template_name = "ujjwala/i_web_form.html"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response


# Whatsapp Nic Error Update Addres View
class WhatsappNicErrorUpdateAddress(View):
    def get(self, request, *args, **kwargs):
        obj = UjjwalaV2Application.objects.filter(pk=kwargs.get('pk')).first()
        if obj:
            obj.event_whatsapp_nic_error_update_address()
            return HttpResponse("Application Id {}: Message Sent".format(kwargs.get('pk')))
        return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))


# Pre Inspection Type Self
class WhatsappPreInspectionTypeSelf(View):
    def get(self, request, *args, **kwargs):
        application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()

        if not application:
            return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))

        if not is_pre_inspection_applicable(application.id):
            return HttpResponse("Application Id {} not valid for Pre-Inspection".format(kwargs.get('pk')))

        pi_obj = PreInspection.objects.filter(parent_id=kwargs.get('pk')).first()
        if not pi_obj:
            pi_obj = PreInspection.objects.create(
                parent_id=application.id,
                status=PreInspectionStatusEnum.KITCHEN_PHOTO,
                type=PreInspectionTypeEnum.SELF
            )
        if pi_obj.status not in (
                PreInspectionStatusEnum.SUBMITTED, PreInspectionStatusEnum.ACCEPTED
        ):
            pi_obj.parent.event_whatsapp_pre_inspection_type_self_admin(pi_obj.id)
            return HttpResponse(
                "Application Id {} Whatsapp Message Sent.".format(kwargs.get('pk'))
            )

        else:
            return HttpResponse(
                "Application Id {} not authorised for self inspection.".format(kwargs.get('pk'))
            )


# This View Shares Web Form Link To The Given Contact Number
@method_decorator(login_required, 'dispatch')
class ShareWebFormLink(TemplateView):
    template_name = "ujjwala/share_web_form_link.html"

    def post(self, request, *args, **kwargs):
        contact_mobile = request.POST.get('contact_mobile', '')

        if contact_mobile:
            application = UjjwalaV2Application.objects.filter(
                contact_mobile=contact_mobile
            ).exclude(
                status=UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD
            ).first()

            if application:
                messages.add_message(
                    request, messages.ERROR, "Application already exist."
                )
            else:
                user = get_current_user()
                res = send_ujjwala_application_whatsapp_link_v2(contact_mobile, user.id)
                if res:
                    messages.add_message(
                        request, messages.INFO,
                        "Ujjwala Application Link Shared To Contact Mobile: {}".format(
                            contact_mobile
                        )
                    )
        return super().get(request, *args, **kwargs)


class UjjwalaApplicationSharedLinkView(View):
    def get(self, request, *args, **kwargs):
        data = kwargs.get('data', '')
        signer = Signer()
        data = base64.urlsafe_b64decode(data)
        data = eval(signer.unsign(data.decode('ascii')))
        application = UjjwalaV2Application.objects.filter(contact_mobile=data['contact_mobile']).first()
        if application:
            if not application.status == UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD:
                return HttpResponse(
                    content="An application already exist with id: {}".format(application.id)
                )
        user = User.objects.filter(id=data['user']).first()
        data.update({
            "source": "link_share",
            "signed_contact_mobile": signer.sign(data['contact_mobile']),
            "referral_code": "{} ({} {})".format(user.username, user.first_name, user.last_name)
        })
        return render(request, template_name='ujjwala/web_form.html', context=data)


class ApplicationView(View):

    def get_object(self, queryset=None):
        try:
            obj = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No Application Exist For Given Application Id"
            )
        return obj


# This View Shares Web Form Link To The Given Contact Number
@method_decorator(login_required, 'dispatch')
class ShareSelfPreInspectionLink(View):

    def get(self, request, *args, **kwargs):
        id = kwargs.get('pk')

        application = UjjwalaV2Application.objects.get(id=id)

        pi = PreInspection.objects.filter(parent_id=application.id)

        if not pi:
            PreInspection.objects.create(
                parent_id=application.id,
                status=PreInspectionStatusEnum.KITCHEN_PHOTO,
                type=PreInspectionTypeEnum.SELF
            )

        if application.pre_inspection.status in (
            PreInspectionStatusEnum.SUBMITTED, PreInspectionStatusEnum.ACCEPTED
        ):
            return HttpResponse(
                "Pre-Inspection Status: {}".format(application.pre_inspection.status)
            )
        else:
            user = get_current_user()
            res = send_ujjwala_self_pre_inspection_share_link(
                application.contact_mobile, user.id, user.username, application
            )
            if res:
                return HttpResponse(
                    "Self Pre-Inspection Link Shared For Application Id: {}".format(id)
                )


@method_decorator(login_required, 'dispatch')
class UserDashboardView(TemplateView):

    template_name = "ujjwala/user_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = get_current_user()

        context.update({
            "user": user,
            "ujjwala_queryset": UjjwalaV2Application.objects.filter(filled_by=user),
            "ujjwala_rejected": UjjwalaV2Application.objects.filter(filled_by=user,
                                                                    status=UjjwalaV2ApplicationStatus.APPLICATION_REJECTED),
            "ujjwala_material_delivered": UjjwalaV2Application.objects.filter(filled_by=user, status__in=[
                UjjwalaV2ApplicationStatus.MATERIAL_DELIVERED, UjjwalaV2ApplicationStatus.INSTALLED
                                                                              ]),
            "preinspection_queryset": PreInspection.objects.filter(mechanic=user),
            "preinspection_accepted": PreInspection.objects.filter(mechanic=user,
                                                                   status=PreInspectionStatusEnum.ACCEPTED),
            "preinspection_rejected": PreInspection.objects.filter(mechanic=user,
                                                                   status=PreInspectionStatusEnum.REJECTED),
        })
        return context


class SharedSelfPreInspectionLinkView(View):

    def get(self, request, *args, **kwargs):
        data = kwargs.get('data', '')

        if data:
            data = unsign_data_base64(data)
            user_id = data.get('user_id', '')
            if user_id:
                user_id = sign_data_base64(data['user_id'])

            response = redirect(
                reverse('ujjwala:pre_inspection_form_view',
                        args=('self', data['pre_inspection_id'])) + '?referral_user_id={}'.format(user_id)
                )
        else:
            response = redirect(
                reverse('ujjwala:pre_inspection_form_view',
                        args=('self', data['pre_inspection_id']))
            )
        return response


class WhatsappUploadLegalForms(View):
    def get(self, request, *args, **kwargs):
        application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()
        if not application:
            return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))

        connection_disbursement = ConnectionDisbursement.objects.filter(parent_id=kwargs.get('pk')).first()

        if connection_disbursement:
            if connection_disbursement.status == ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING:
                application.event_legal_documents_upload_channel_whatsapp()
                return HttpResponse(
                    "Application Id {} Form A B C sent.".format(kwargs.get('pk'))
                )
            else:
                return HttpResponse(
                    "Application Id {} Form A B C Uploaded.".format(kwargs.get('pk'))
                )
        else:
            return HttpResponse(
                "Application Id {} not valid state. Connection Disbursement not created.".format(kwargs.get('pk'))
            )


class ResetRoboFailedCount(View):
    def get(self, request, *args, **kwargs):
        application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()
        if not application:
            return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))
        application.robo_execution_failed_count = 0
        application.save()
        return HttpResponse(
            "Application Id {} Robo Execution Failed Count Set To Zero".format(kwargs.get('pk'))
        )


class WhatsappUpdateBankDetailsView(View):
    def get(self, request, *args, **kwargs):
        application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()
        if not application:
            return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))

        if not application.ifsc_code:
            application.event_whatsapp_update_bank_details()
            return HttpResponse(
                "Update Bank Details Message Sent For Application Id: {}".format(kwargs.get('pk'))
            )
        else:
            return HttpResponse(
                "Bank Details Already Uploaded For Application Id: {}".format(kwargs.get('pk'))
            )


class ApplicationStatusView(DetailView):
    model = UjjwalaV2Application

    def get_template_names(self):
        return 'ujjwala/status.html'


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationWebFormView(TemplateView):
    template_name = "ujjwala/web_form.html"

    # def get_context_data(self, **kwargs):
    #     context_data = super().get(**kwargs)
    #     form_fill_area_list = FormFillArea.objects.all()
    #     context_data = context_data.update({
    #         "form_fill_area_list": form_fill_area_list
    #     })
    #     return context_data


@method_decorator(login_required, 'dispatch')
class UjjwalaPreInspectionListView(ListView):
    model = PreInspection

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        return PreInspection.objects.filter(
            mechanic=get_current_user()
        ).order_by('-submitted_on')

    def get_template_names(self):
        return 'ujjwala/pre-inspection/pre_inspection_listview.html'


@method_decorator(login_required, 'dispatch')
class PreInspectionReviewListView(ListView):
    model = PreInspection

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        return PreInspection.objects.filter(
            status=PreInspectionStatusEnum.SUBMITTED
        )

    def get_template_names(self):
        return 'ujjwala/review/pre_inspection_review_listview.html'


@method_decorator(login_required, 'dispatch')
class PreInspectionReviewView(FormView, ApplicationView):
    model = PreInspection
    template_name = 'ujjwala/review/pre_inspection_review.html'
    form_class = PreInspectionReviewAdminForm

    def get_success_url(self):
        return reverse('ujjwala:pre_inspection_review_list')

    def dispatch(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_reviewer_group(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            pre_inspection = self.get_object()
            if pre_inspection.status != PreInspectionStatusEnum.SUBMITTED:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} - {}".format(
                        pre_inspection.parent_id, pre_inspection.get_status_display()
                    )
                )
                return redirect('ujjwala:installation_review')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        try:
            obj = PreInspection.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No Application Exist For Given Application Id"
            )
        return obj

    def form_valid(self, form):
        obj = self.get_object()
        data = form.cleaned_data
        obj.pre_inspection_review(
            review_status=data['review_status'],
            rejected_reason=data['rejected_reason'],
            by=get_current_user(),
            description='{} - {}'.format(data.get('review_status'), data.get('rejected_reason' ''))
        )
        obj.save()
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # connection_disbursement = self.get_object()
        # kwargs['connection_disbursement'] = connection_disbursement
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()

        kitchen_photo = obj.documents.filter(
                type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO
            ).first().link

        main_gate = obj.documents.filter(
                type=UjjwalaApplicationDocumentsEnum.MAIN_GATE
            ).first().link

        context.update({
            "obj": obj,
            "kitchen_photo": kitchen_photo,
            "main_gate": main_gate,
        })

        if obj.type == PreInspectionTypeEnum.MECHANIC:
            context.update({
                "audio_file": obj.documents.get(
                    type=UjjwalaApplicationDocumentsEnum.SAFETY_AUDIO
                ).link
            })
        return context


class UjjwalaApplicationDisplayOtp(View):
    model = Otp

    def get(self, request, *args, **kwargs):
        obj = Otp.objects.filter(reference_number=kwargs.get('ref_no')).first()

        if obj:
            return render(self.request, "ujjwala/otp/ujjwala_application_display_otp.html", {
                "obj": obj
            })
        else:
            return HttpResponse(content="Invalid Reference Number")


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationReuploadFormView(FormView):
    form_class = UjjwalaDocumentsReuploadForm

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super().get_initial()

        initial['application_id'] = self.kwargs.get('pk')

        return initial


@method_decorator(login_required_if_mech_inspection, 'dispatch')
class PreInspectionView(FormView):
    model = PreInspection
    pre_inspection_step0_template = 'ujjwala/pre-inspection/steps/step0.html'
    pre_inspection_step1_template = 'ujjwala/pre-inspection/steps/step1.html'
    pre_inspection_step2_template = 'ujjwala/pre-inspection/steps/step2.html'
    pre_inspection_step3_template = 'ujjwala/pre-inspection/steps/step3.html'
    success_url = '.'

    stage_1_generate_otp = 'ujjwala/pre-inspection/pre_inspection_generate_otp_form.html'
    stage_2_validate_otp = 'ujjwala/pre-inspection/pre_inspection_validate_otp_form.html'

    def dispatch(self, request, *args, **kwargs):
        pre_inspection = self.get_object()
        if pre_inspection.status in (
                PreInspectionStatusEnum.SUBMITTED,
                PreInspectionStatusEnum.ACCEPTED,
        ):
            return render(self.request, 'ujjwala/pre-inspection/pre_inspection_status.html', context={
                'pre_inspection': pre_inspection
            })

        if self.kwargs.get('type') == 'mech':
            if pre_inspection.status == PreInspectionStatusEnum.ALLOCATED \
                    or (pre_inspection.status in (PreInspectionStatusEnum.REJECTED, PreInspectionStatusEnum.REDO)
                        and pre_inspection.type == PreInspectionTypeEnum.MECHANIC
            ):
                return self.otp_verification(pre_inspection)
                # return HttpResponse("<h1>Ujjwala Pre-Inspection Currently On Hold</h1>")

        return super().dispatch(request, *args, **kwargs)

    def otp_verification(self, pre_inspection):
        context = {'pre_inspection': pre_inspection, 'application': pre_inspection.parent}
        if self.request.method.lower() == 'get':
            app = pre_inspection.parent
            context.update({
                'form': PreInspectionAllocatedGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    initial={
                        'pre_inspection_id': pre_inspection.id,
                        'application_id': pre_inspection.parent_id
                    }
                )
            })
            return render(self.request, self.stage_1_generate_otp, context)
        elif self.request.method.lower() == 'post':
            if self.request.POST.get('form_type') == 'generate_otp_form':
                app = UjjwalaV2Application.objects.get(pk=pre_inspection.parent_id)
                form = PreInspectionAllocatedGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    data=self.request.POST,
                )
                if not form.is_valid():
                    context.update({
                        'form': form
                    })
                    return render(self.request, self.stage_1_generate_otp, context)
                otp_obj = form.send_otp()
                app_id = form.data.get('application_id')
                context.update({
                    'form': PreInspectionAllocatedValidateOtpForm(
                        initial={
                            'application_id': app_id,
                            'reference_number': otp_obj.reference_number,
                            'mobile': otp_obj.mobile
                        }
                    )
                })
                return render(self.request, self.stage_2_validate_otp, context)
            elif self.request.POST.get('form_type') == 'validate_otp_form':
                form = PreInspectionAllocatedValidateOtpForm(data=self.request.POST)
                otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
                if not form.is_valid():
                    context.update({
                        'form': PreInspectionAllocatedValidateOtpForm(
                            initial={
                                'application_id': pre_inspection.parent_id,
                                'reference_number': otp_obj.reference_number,
                                'mobile': otp_obj.mobile
                            }
                        )
                    })
                    return render(self.request, self.stage_2_validate_otp, context)
                if pre_inspection.type == PreInspectionTypeEnum.SELF:
                    pre_inspection.pre_inspection_otp_verified(
                        description="Allocated Inspection Otp Verified, Customer Phone {}".format(otp_obj.mobile)
                    )
                    pre_inspection.save()

                    pre_inspection.pre_inspection_change_address(
                        description="Skipped By Admin, Change Address"
                    )
                    pre_inspection.save()
                    return redirect('ujjwala:pre_inspection_form_view', type='self', pk=pre_inspection.id)
                else:
                    pre_inspection.pre_inspection_otp_verified(
                        by=get_current_user(),
                        description="Allocated Inspection Otp Verified, Customer Phone {}".format(otp_obj.mobile)
                    )
                    pre_inspection.save()

                    pre_inspection.pre_inspection_change_address(
                        by=get_current_user(),
                        description="Skipped By Admin, Change Address"
                    )
                    pre_inspection.save()
                    return redirect('ujjwala:pre_inspection_form_view', type='mech', pk=pre_inspection.id)

    def get_object(self, queryset=None):
        try:
            obj = PreInspection.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No %(verbose_name)s found matching the query" %
                {'verbose_name': queryset.model._meta.verbose_name}
            )
        return obj

    def get_form_class(self):
        application = self.get_object()
        if application.status == PreInspectionStatusEnum.CHANGE_ADDRESS:
            return ChangeAddressForm
        elif application.status in (
                PreInspectionStatusEnum.KITCHEN_PHOTO,
                PreInspectionStatusEnum.REJECTED,
                PreInspectionStatusEnum.REDO
        ):
            return KitchenPreInspectionForm
        elif application.status == PreInspectionStatusEnum.SAFETY_AUDIO:
            return AudioOnSafetyForm
        elif application.status == PreInspectionStatusEnum.PREVIEW_INSPECTION:
            return PreviewPreInspectionForm

    def form_valid(self, form):
        form.save()
        if form.__class__ == PreviewPreInspectionForm:
            obj = self.get_object()
            if obj.type == PreInspectionTypeEnum.SELF:
                referral_user_id = self.request.GET.get('referral_user_id', '')
                if referral_user_id:
                    referral_user_id = unsign_data_base64(referral_user_id)
                    obj.referral_user_id = referral_user_id
                else:
                    obj.referral_user_id = None
                obj.save()

                response = HttpResponse(
                    content="<h1>Pre-Inspection Submitted For Review</h1>"
                )
                return response

        return HttpResponseRedirect(
            self.get_success_url() + '?referral_user_id={}'.format(self.request.GET.get('referral_user_id', ''))
        )

    def get_template_names(self):
        pre_inspection_obj = self.get_object()
        if pre_inspection_obj.status == PreInspectionStatusEnum.CHANGE_ADDRESS:
            return self.pre_inspection_step0_template
        elif pre_inspection_obj.status in (
                PreInspectionStatusEnum.KITCHEN_PHOTO,
                PreInspectionStatusEnum.REJECTED,
                PreInspectionStatusEnum.REDO,
        ):
            return self.pre_inspection_step1_template
        elif pre_inspection_obj.status == PreInspectionStatusEnum.SAFETY_AUDIO:
            return self.pre_inspection_step2_template
        elif pre_inspection_obj.status == PreInspectionStatusEnum.PREVIEW_INSPECTION:
            return self.pre_inspection_step3_template

    # def get_form(self, form_class=None):
    #     form = super().get_form(form_class=form_class)
    #     if form.__class__ == ChangeAddressForm:
    #         form = ChangeAddressForm(initial=form.pre_inspection.parent.address_json)
    #     return form

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        pre_inspection = self.get_object()
        kwargs['pre_inspection'] = pre_inspection
        if pre_inspection.status == PreInspectionStatusEnum.CHANGE_ADDRESS:
            kwargs['initial'] = pre_inspection.parent.address_json
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        referral_user_id = self.request.GET.get('referral_user_id', '')

        if referral_user_id:
            referral_user_id = unsign_data_base64(referral_user_id)
            user = User.objects.filter(id=referral_user_id).first()
        else:
            user = None

        context.update({
            "obj": self.get_object(),
            "referral_user": user
        })

        return context


@method_decorator(login_required, 'dispatch')
class PreInspectionCreateView(View):
    model = PreInspection
    stage_1_template = 'ujjwala/pre-inspection/pre_inspection_initial_form.html'
    stage_2_template = 'ujjwala/pre-inspection/pre_inspection_generate_otp_form.html'
    stage_3_template = 'ujjwala/pre-inspection/pre_inspection_validate_otp_form.html'

    def get(self, request, *args, **kwargs):
        return render(self.request, self.stage_1_template, {
            'form': PreInspectionInitialForm()
        })

    def post(self, request, *args, **kwargs):
        if self.request.POST.get('form_type') == 'initial_form':
            form = PreInspectionInitialForm(data=request.POST)

            if not form.is_valid():
                return render(self.request, self.stage_1_template, {
                    'form': form
                })
            app_id = form.data.get('application_id')

            # pre_inspection_obj = PreInspection.objects.filter(
            #     parent_id=app_id
            # ).exclude(
            #     status__in=[
            #         PreInspectionStatusEnum.REJECTED
            #     ]
            # ).first()

            pre_inspection_obj = PreInspection.objects.filter(
                parent_id=app_id
            ).first()

            if pre_inspection_obj:
                if pre_inspection_obj.status != PreInspectionStatusEnum.REJECTED:
                    if pre_inspection_obj.type == PreInspectionTypeEnum.SELF:
                        return redirect(
                            'ujjwala:pre_inspection_form_view', type='self', pk=pre_inspection_obj.pk
                        )
                    elif pre_inspection_obj.type == PreInspectionTypeEnum.MECHANIC:
                        return redirect(
                            'ujjwala:pre_inspection_form_view', type='mech',
                            pk=pre_inspection_obj.pk
                        )

            app = UjjwalaV2Application.objects.filter(pk=app_id).first()
            return render(self.request, self.stage_2_template, {
                'form': PreInspectionGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    initial={
                        'application_id': app_id
                    }
                ),
                'application': UjjwalaV2Application.objects.get(pk=app_id)
            })
        elif self.request.POST.get('form_type') == 'generate_otp_form':
            app_id = self.request.POST.get('application_id')
            app = UjjwalaV2Application.objects.filter(pk=app_id).first()
            form = PreInspectionGenerateOtpForm(
                mobile_nos=app.all_contacts,
                data=request.POST
            )
            if not form.is_valid():
                return render(self.request, self.stage_2_template, {
                    'form': form,
                    'application': app,
                })
            otp_obj = form.send_otp()
            app_id = form.data.get('application_id')
            return render(self.request, self.stage_3_template, {
                'form': PreInspectionValidateOtpForm(
                    initial={
                        'application_id': app_id,
                        'reference_number': otp_obj.reference_number,
                        'mobile': otp_obj.mobile
                    }),
            })
        elif self.request.POST.get('form_type') == 'validate_otp_form':
            form = PreInspectionAllocatedValidateOtpForm(data=request.POST)
            otp_obj = Otp.objects.filter(reference_number=request.POST['reference_number']).first()
            if not form.is_valid():
                return render(self.request, self.stage_3_template, {
                    'form': form,
                    'reference_number': otp_obj.reference_number,
                    'mobile': otp_obj.mobile
                })

            app_id = form.data.get('application_id')
            obj = PreInspection.objects.filter(
                parent_id=app_id
            ).first()

            if obj:
                obj.type = PreInspectionTypeEnum.MECHANIC
            else:
                obj = PreInspection.objects.create(
                    parent_id=app_id,
                    status=PreInspectionStatusEnum.ALLOCATED,
                    type=PreInspectionTypeEnum.MECHANIC,
                    mechanic=get_current_user()
                )

            obj.pre_inspection_otp_verified(
                by=get_current_user(),
                description="Instant Inspection Created, Customer Phone {}".format(otp_obj.mobile)
            )
            obj.save()

            obj.pre_inspection_change_address(
                by=get_current_user(),
                description="Skipped By Admin, Customer Address"
            )
            obj.save()

            return redirect('ujjwala:pre_inspection_form_view', type='mech', pk=obj.pk)


class ReviewForm(forms.ModelForm):
    action = forms.ChoiceField(
        widget=forms.Select,
        choices=(
            ("A", "Accept"),
            ("R", "Reject")
        ),
        required=False
    )
    remarks = forms.CharField(widget=forms.TextInput)

    class Meta:
        from ujjwala.models import PreInspection
        model = PreInspection
        fields = ('id', 'action', 'remarks')


class UjjwalaApplicationLegalDocumentsUpload(FormView):
    form_class = UjjwalaLegalDocumentsUpload
    template_name = "ujjwala/legal-document-upload-form.html"

    def dispatch(self, request, *args, **kwargs):
        connection_disbursement = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))

        if connection_disbursement.status not in (
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
        ):
            return HttpResponse(content='Status: {}'.format(connection_disbursement.status))

        return super().dispatch(request, *args, **kwargs)
        # return redirect('ujjwala:legal_documents_upload', pk=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # application = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
        connection_disbursement = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))
        context.update({
            "obj": connection_disbursement
        })
        return context


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationStatusView(TemplateView):
    template_name = "ujjwala/application_status/application_search_status.html"

    def get(self, request, *args, **kwargs):
        contact_mobile = request.GET.get('contact_mobile', '')
        uid = request.POST.get('uid', '')
        application_id = request.GET.get('application_id', '')
        application = {}

        if contact_mobile:
            application = UjjwalaV2Application.objects.filter(contact_mobile=contact_mobile).first()
        elif uid:
            family_member = FamilyMembers.objects.filter(uid_no=uid).first()
            if family_member:
                application = family_member.parent
        elif application_id:
            application = UjjwalaV2Application.objects.filter(id=application_id).first()

        if application:
            reject_reason = ujjwala_application_reject_reason_log(application.id)
            return render(request, self.template_name, context={'obj': application, 'rejected_reason': reject_reason})
        else:
            messages.add_message(
                request, messages.ERROR, "Please Enter Contact Mobile Or Aadhaar Or Application Id To Search"
            )
        return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 100
    permission = 'has_view_permission'

    def get_queryset(self):
        disbursement_drive = get_current_user_disbursement_drive(get_current_user())

        return ConnectionDisbursement.objects.filter(
            status__in=[
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
                ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
                ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
            ],
            walk_in_date__date=datetime.datetime.today().date(),
            disbursement_drive=disbursement_drive
        ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/disbursement/connection_disbursement_listview.html'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(self.request, 'ujjwala/no_permissions.html')
        disbursement_drive = DisbursementDrive.objects.filter(
            team_members=user, status=DisbursementDriveStatusEnum.ACTIVE
        ).first()

        connection_disbursement_count = ConnectionDisbursement.objects.filter(
            disbursement_drive=disbursement_drive
        ).exclude(walk_in_date=None).count()

        context.update({
            "current_disbursement_index": connection_disbursement_count,
            "max_walkins": disbursement_drive.max_walk_ins,
            "disbursement_drive": disbursement_drive
        })
        return context

    def get(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            disbursement_drive = DisbursementDrive.objects.filter(
                date__lte=datetime.datetime.now().date(), status=DisbursementDriveStatusEnum.ACTIVE
            ).first()
            if not disbursement_drive:
                messages.add_message(
                    request, messages.INFO, "No Active Disbursement Drive Exist"
                )
            else:
                obj = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
                if obj:
                    if obj.status not in disbursement_drive.legal_documents_conditions:
                        messages.add_message(
                            request, messages.ERROR, "Application Id: {} - {}".format(
                                application_id, obj.status
                            )
                        )
                    else:
                        return redirect('ujjwala:connection_disbursement_form_view', pk=obj.pk)
                else:
                    messages.add_message(
                        request, messages.ERROR, "Application Id: {} not found".format(application_id)
                    )
        return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementView(TemplateView, ApplicationView):
    model = ConnectionDisbursement
    walk_in_template = 'ujjwala/disbursement/forms/walk_in_confirmation.html'
    ujjwala_form_a_b_c_template = "ujjwala/disbursement/print_ujjwala_form_a_b_c.html"
    success_url = '.'

    stage_1_generate_otp = 'ujjwala/disbursement/otp/generate_otp_form.html'
    # stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
    stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'

    def dispatch(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        disbursement_drive = DisbursementDrive.objects.filter(
            status=DisbursementDriveStatusEnum.ACTIVE, team_members=user
        ).first()

        if not disbursement_drive:
            messages.add_message(
                request, messages.INFO,
                f"No Active Disbursement Drive. For Help Contact Manager - {disbursement_drive.manager.first_name} {disbursement_drive.manager.last_name}."
            )
            return redirect('ujjwala:connection_disbursement_list')
        if not datetime.datetime.today().date() == disbursement_drive.date:
            messages.add_message(
                request, messages.INFO,
                f"Please Close Existing Disbursement Drive. For Help Contact Manager - {disbursement_drive.manager.first_name} {disbursement_drive.manager.last_name}."
            )
            return redirect('ujjwala:connection_disbursement_list')

        connection_disbursement_count = ConnectionDisbursement.objects.filter(
            disbursement_drive=disbursement_drive
        ).exclude(walk_in_date=None).count()

        if connection_disbursement_count == disbursement_drive.max_walk_ins:
            messages.add_message(
                request, messages.INFO,
                "Max Walk-ins for Disbursement Drive achieved."
            )
            return redirect('ujjwala:connection_disbursement_list')
        connection_disbursement = self.get_object()

        if connection_disbursement:
            if not connection_disbursement.parent.ekyc_cleared:
                messages.add_message(
                    request, messages.ERROR,
                    "Application Id : {} Status: {} Pre-Inspection Status: {} Ekyc Cleared: {}".format(
                        connection_disbursement.parent_id, connection_disbursement.parent.get_status_display(),
                        connection_disbursement.parent.pre_inspection.get_status_display(),
                        connection_disbursement.parent.ekyc_cleared
                    )
                )
            elif connection_disbursement.parent.status in (
                    UjjwalaV2ApplicationStatus.NIC_CLEARED,
                    UjjwalaV2ApplicationStatus.READY_FOR_DISBURSEMENT,
                    UjjwalaV2ApplicationStatus.NIC_CLEARED_SDMS_RELATION_CANCELLED
            ):
                if not connection_disbursement.walk_in_date or \
                        (connection_disbursement.walk_in_date.date() != datetime.datetime.today().date()):
                    return self.otp_verification(connection_disbursement)
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id : {} Status: {}".format(
                        connection_disbursement.parent_id, connection_disbursement.parent.get_status_display()
                    )
                )
        else:
            pi_obj = PreInspection.objects.filter(
                parent_id=self.kwargs.get('pk')).first()

            if pi_obj:
                messages.add_message(
                    request, messages.ERROR, "Application Id : {} Pre Inspection Status: {}".format(
                        pi_obj.parent_id, pi_obj.get_status_display()
                    )
                )
        return super().dispatch(request, *args, **kwargs)

    def otp_verification(self, connection_disbursement):
        context = {'connection_disbursement': connection_disbursement, 'application': connection_disbursement.parent}

        if self.request.method.lower() == 'get':
            app = connection_disbursement.parent
            context.update({
                'form': UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    initial={
                        'connection_disbursement_id': connection_disbursement.id,
                        'application_id': connection_disbursement.parent_id,
                        'whatsapp_template_name': 'connection_disbursement_dac',
                        'otp_generated_for': f'connectiondisbursement:{connection_disbursement.id}:Walk-In',
                    }
                )
            })
            return render(self.request, self.stage_1_generate_otp, context)
        elif self.request.method.lower() == 'post':
            if self.request.POST.get('form_type') == 'generate_otp_form':
                app = UjjwalaV2Application.objects.get(pk=connection_disbursement.parent_id)
                form = UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    data=self.request.POST,
                )
                if not form.is_valid():
                    context.update({
                        'form': form
                    })
                    return render(self.request, self.stage_1_generate_otp, context)
                otp_obj = form.send_otp()
                app_id = form.data.get('application_id')
                context.update({
                    'form': UjjwalaApplicationValidateOtpForm(
                        initial={
                            'application_id': app_id,
                            'reference_number': otp_obj.reference_number,
                            'mobile': otp_obj.mobile
                        }
                    )
                })
                return render(self.request, self.stage_2_validate_otp, context)
            elif self.request.POST.get('form_type') == 'validate_otp_form':
                form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
                otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
                if not form.is_valid():
                    context.update({
                        'form': UjjwalaApplicationValidateOtpForm(
                            initial={
                                'application_id': connection_disbursement.parent_id,
                                'reference_number': otp_obj.reference_number,
                                'mobile': otp_obj.mobile
                            }
                        )
                    })
                    return render(self.request, self.stage_2_validate_otp, context)

                disbursement_drive = get_current_user_disbursement_drive(get_current_user())

                connection_disbursement.walk_in_date = datetime.datetime.now()
                connection_disbursement.disbursement_drive = disbursement_drive
                connection_disbursement.save()

                send_ujjwala_share_on_social_media_link(self.request, connection_disbursement.parent.contact_mobile,
                                                        connection_disbursement.parent
                                                        )
                return HttpResponseRedirect('.')

    def get_template_names(self):
        connection_disbursement = self.get_object()
        if not connection_disbursement.walk_in_date or \
                (connection_disbursement.walk_in_date.date() != datetime.datetime.today().date()):
            return self.walk_in_template
        return self.ujjwala_form_a_b_c_template

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    # def form_valid(self, form):
    #     return redirect('ujjwala:connection_disbursement_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "obj": self.get_object()
        })
        return context


# @method_decorator(login_required, 'dispatch')
class UjjwalaApplicationCustomerProfileView(TemplateView):
    template_name = 'ujjwala/extra/ujjwala_customer_profile.html'

    stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
    stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'

    def get_object(self, queryset=None):
        try:
            obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No Application Exist For Given Application Id"
            )
        return obj

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()

        user = get_current_user()
        if user.is_anonymous:
            return self.otp_verification(obj)
        return super().dispatch(request, *args, **kwargs)

    def otp_verification(self, application):
        context = {'application': application}

        if self.request.method.lower() == 'get':
            app = application
            context.update({
                'form': UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    initial={
                        'application_id': application.id,
                        'whatsapp_template_name': 'connection_disbursement_dac',
                        'otp_generated_for': f'ujjwalav2application:{application.id}:View-Customer-Profile',
                    }
                )
            })
            return render(self.request, self.stage_1_generate_otp, context)
        elif self.request.method.lower() == 'post':
            if self.request.POST.get('form_type') == 'generate_otp_form':
                app = application
                form = UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    data=self.request.POST,
                )
                if not form.is_valid():
                    context.update({
                        'form': form
                    })
                    return render(self.request, self.stage_1_generate_otp, context)
                otp_obj = form.send_otp()
                app_id = form.data.get('application_id')
                context.update({
                    'form': UjjwalaApplicationValidateOtpForm(
                        initial={
                            'application_id': app_id,
                            'reference_number': otp_obj.reference_number,
                            'mobile': otp_obj.mobile
                        }
                    )
                })
                return render(self.request, self.stage_2_validate_otp, context)
            elif self.request.POST.get('form_type') == 'validate_otp_form':
                form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
                otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
                if not form.is_valid():
                    context.update({
                        'form': UjjwalaApplicationValidateOtpForm(
                            initial={
                                'application_id': application.id,
                                'reference_number': otp_obj.reference_number,
                                'mobile': otp_obj.mobile
                            }
                        )
                    })
                    return render(self.request, self.stage_2_validate_otp, context)

                return render(self.request, self.template_name, {'obj': application})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "obj": self.get_object()
        })
        return context


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementReviewFormAbcListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 100
    permission = 'has_view_permission'

    def get_queryset(self):
        disbursement_drive = get_current_user_disbursement_drive(get_current_user())
        return ConnectionDisbursement.objects.filter(
            status__in=[
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
            ],
            walk_in_date__date=datetime.datetime.today().date(),
            disbursement_drive=disbursement_drive
        ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/disbursement/forms/connection_disbursement_review_form_abc_listview.html'

    def get(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if object:
                if object.status not in (
                        ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
                ):
                    messages.add_message(
                        request, messages.ERROR, "Application Id: {} - {}".format(
                            application_id, object.get_status_display()
                        )
                    )
                else:
                    return redirect('ujjwala:connection_disbursement_review_form_abc_view',
                                    pk=object.pk)
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        disbursement_drive = DisbursementDrive.objects.filter(
            team_members=get_current_user(), status=DisbursementDriveStatusEnum.ACTIVE
        ).first()

        connection_disbursement_count = ConnectionDisbursement.objects.filter(
            disbursement_drive=disbursement_drive
        ).exclude(walk_in_date=None).count()

        context.update({
            "current_disbursement_index": connection_disbursement_count,
            "max_walkins": disbursement_drive.max_walk_ins,
            "disbursement_drive": disbursement_drive
        })
        return context


# Step - 2 Review Form A B C
@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementReviewFormAbcView(FormView, ApplicationView):
    model = ConnectionDisbursement
    template_name = 'ujjwala/disbursement/forms/review_form_abc.html'
    form_class = LegalDocumentsReviewAdminForm

    def get_success_url(self):
        if '_back_list_view' in self.request.POST:
            return reverse('ujjwala:connection_disbursement_review_form_abc_list')
        if '_next_form_view' in self.request.POST:
            obj = self.get_object()
            return reverse(
                'ujjwala:connection_disbursement_sv_label_print_view',
                kwargs={'pk': obj.pk}
            )
        return '.'

    def dispatch(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            connection_disbursement = self.get_object()
            if connection_disbursement.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} - {}".format(
                        connection_disbursement.parent_id, connection_disbursement.get_status_display()
                    )
                )
                return redirect('ujjwala:connection_disbursement_review_form_abc_list')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def form_valid(self, form):
        obj = self.get_object()
        data = form.cleaned_data
        obj.transition_legal_documents_reviewed(
            review_status=data['review_status'],
            by=get_current_user(),
            description='{} - {}'.format(data.get('review_status'), data.get('rejected_reason' ''))
        )
        obj.save()
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # connection_disbursement = self.get_object()
        # kwargs['connection_disbursement'] = connection_disbursement
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        form_abc = obj.parent.get_form_abc()
        context.update({
            "obj": obj,
            "form_abc": form_abc
        })
        return context


# Step - 3 SV Label Print List View & Form View
@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementSvLabelPrintListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        disbursement_drive = get_current_user_disbursement_drive(get_current_user())

        qs = ConnectionDisbursement.objects.filter(
            status__in=[
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
            ],
            walk_in_date__date=datetime.datetime.today().date(),
            disbursement_drive=disbursement_drive
        ).prefetch_related('invitation').order_by('updated_on')
        return qs

    def get_template_names(self):
        return 'ujjwala/disbursement/forms/connection_disbursement_sv_label_print_listview.html'

    def get(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if object:
                if not object.walk_in_date:
                    messages.add_message(
                        request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
                            object.parent_id, object.get_status_display()
                        )
                    )
                    return redirect('ujjwala:connection_disbursement_sv_label_print_list')
                if object.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED:
                    messages.add_message(
                        request, messages.ERROR, "Application Id: {} - {}".format(
                            application_id, object.get_status_display()
                        )
                    )
                else:
                    return redirect(
                        'ujjwala:connection_disbursement_sv_label_print_view',
                        pk=object.pk
                    )
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        disbursement_drive = DisbursementDrive.objects.filter(
            team_members=get_current_user(), status=DisbursementDriveStatusEnum.ACTIVE
        ).first()

        connection_disbursement_count = ConnectionDisbursement.objects.filter(
            disbursement_drive=disbursement_drive
        ).exclude(walk_in_date=None).count()

        context.update({
            "current_disbursement_index": connection_disbursement_count,
            "max_walkins": disbursement_drive.max_walk_ins,
            "disbursement_drive": disbursement_drive
        })
        return context


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementSvLabelPrintView(FormView, ApplicationView):
    model = ConnectionDisbursement
    template_name = 'ujjwala/disbursement/forms/sv_label_print.html'
    form_class = ConnectionDisbursementSvLabelPrintForm

    def get_success_url(self):
        if '_back_list_view' in self.request.POST:
            return reverse('ujjwala:connection_disbursement_sv_label_print_list')
        if '_next_form_view' in self.request.POST:
            return reverse('ujjwala:connection_disbursement_sv_label_print_list')
            # obj = self.get_object()
            # return reverse(
            #     'ujjwala:connection_disbursement_social_media_updates_view',
            #     kwargs={'pk': obj.pk}
            # )
        return '.'

    def dispatch(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            connection_disbursement = self.get_object()
            if not connection_disbursement.walk_in_date:
                messages.add_message(
                    request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
                        connection_disbursement.parent_id, connection_disbursement.get_status_display()
                    )
                )
                return redirect('ujjwala:connection_disbursement_sv_label_print_list')
            if connection_disbursement.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} - {}".format(
                        connection_disbursement.parent_id, connection_disbursement.get_status_display()
                    )
                )
                return redirect('ujjwala:connection_disbursement_sv_label_print_list')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def form_valid(self, form):
        form.save()
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        connection_disbursement = self.get_object()
        kwargs['connection_disbursement'] = connection_disbursement
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        bluebook_label_print_url = reverse(
            'ujjwala:connection_disbursement_barcode_label_print_view',
            kwargs={'pk': obj.id}
        )
        context.update({
            "obj": obj,
            "bluebook_label_print_url": self.request.build_absolute_uri(bluebook_label_print_url)
        })
        return context


# Step - 4 Social Media Updates List View & Form View
@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementSocialMediaUpdatesListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        disbursement_drive = get_current_user_disbursement_drive(get_current_user())

        return ConnectionDisbursement.objects.filter(
            # status__in=[
            #     ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
            # ],
            social_media_update_done=False,
            walk_in_date__date=datetime.datetime.today().date(),
            disbursement_drive=disbursement_drive
        ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/disbursement/forms/connection_disbursement_social_media_updates_listview.html'

    def get(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if object:
                if not object.walk_in_date:
                    messages.add_message(
                        request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
                            object.parent_id, object.get_status_display()
                        )
                    )
                    return redirect('ujjwala:connection_disbursement_social_media_updates_list')

                if object.social_media_update_done:
                    messages.add_message(request, messages.ERROR, "Application Id {} Social Media Already Done.")
                    return redirect('ujjwala:connection_disbursement_social_media_updates_list')
                # if object.status != ConnectionDisbursementStatusEnum.SV_LABEL_PRINT:
                #     messages.add_message(
                #         request, messages.ERROR, "Application Id: {} - {}".format(
                #             application_id, object.get_status_display()
                #         )
                #     )
                else:
                    return redirect('ujjwala:connection_disbursement_social_media_updates_view', pk=object.pk)
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        disbursement_drive = DisbursementDrive.objects.filter(
            team_members=get_current_user(), status=DisbursementDriveStatusEnum.ACTIVE
        ).first()

        connection_disbursement_count = ConnectionDisbursement.objects.filter(
            disbursement_drive=disbursement_drive
        ).exclude(walk_in_date=None).count()

        context.update({
            "current_disbursement_index": connection_disbursement_count,
            "max_walkins": disbursement_drive.max_walk_ins,
            "disbursement_drive": disbursement_drive
        })
        return context


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementSocialMediaUpdatesView(FormView, ApplicationView):
    model = ConnectionDisbursement
    template_name = 'ujjwala/disbursement/forms/social_media_updates.html'
    form_class = ConnectionDisbursementSocialMediaUpdatesForm

    def get_success_url(self):
        if '_back_list_view' in self.request.POST:
            return reverse('ujjwala:connection_disbursement_social_media_updates_list')
        if '_next_form_view' in self.request.POST:
            obj = self.get_object()
            # return reverse(
            #     'ujjwala:connection_disbursement_material_delivery_view',
            #     kwargs={'pk': obj.pk}
            # )
            return reverse('ujjwala:connection_disbursement_social_media_updates_list')
        return '.'

    def dispatch(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            connection_disbursement = self.get_object()
            if not connection_disbursement.walk_in_date:
                messages.add_message(
                    request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
                        connection_disbursement.parent_id, connection_disbursement.get_status_display()
                    )
                )
                return redirect('ujjwala:connection_disbursement_social_media_updates_list')
            if connection_disbursement.status != ConnectionDisbursementStatusEnum.SV_LABEL_PRINT:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} - {}".format(
                        connection_disbursement.parent_id, connection_disbursement.get_status_display()
                    )
                )
                return redirect('ujjwala:connection_disbursement_social_media_updates_list')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def form_valid(self, form):
        form.save()
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        connection_disbursement = self.get_object()
        kwargs['connection_disbursement'] = connection_disbursement
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "obj": self.get_object()
        })
        return context


# Step - 4 Material Delivery List View & Form View
@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementMaterialDeliveryListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        disbursement_drive: DisbursementDrive = get_current_user_disbursement_drive(get_current_user())

        if disbursement_drive.social_media_required:
            return ConnectionDisbursement.objects.filter(
                social_media_update_done=True,
                status__in=[
                    # ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
                    ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
                    ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
                ],
                walk_in_date__date=datetime.datetime.today().date(),
                disbursement_drive=disbursement_drive
            ).order_by('updated_on')
        else:
            return ConnectionDisbursement.objects.filter(
                status__in=[
                    # ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
                    ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
                    ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
                ],
                walk_in_date__date=datetime.datetime.today().date(),
                disbursement_drive=disbursement_drive
            ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/disbursement/forms/connection_disbursement_material_delivery_listview.html'

    def get(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')

        if not application_id:
            #Load List View
            return super().get(request, *args, **kwargs)

        object: ConnectionDisbursement = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
        if not object:
            messages.add_message(
                request, messages.ERROR, "Application Id: {} not found".format(application_id)
            )

        if not object.walk_in_date:
            messages.add_message(
                request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
                    object.parent_id, object.get_status_display()
                )
            )
            return redirect('ujjwala:connection_disbursement_material_delivery_list')

        social_step_cleared = True
        if object.disbursement_drive.social_media_required:
            if not object.social_media_update_done:
                social_step_cleared = False

        if object.status == ConnectionDisbursementStatusEnum.SV_LABEL_PRINT and not social_step_cleared:
            messages.add_message(
                request, messages.ERROR, "Social Media Photo Is Pending. Please Upload To Continue"
            )
            return redirect('ujjwala:connection_disbursement_material_delivery_list')

        if object.status not in (
                ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED
        ):
            messages.add_message(
                request, messages.ERROR, "Application Id: {} - {}".format(
                    application_id, object.get_status_display(), object.social_media_update_done
                )
            )
            return redirect('ujjwala:connection_disbursement_material_delivery_list')

        return redirect('ujjwala:connection_disbursement_material_delivery_view', pk=object.pk)


    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        disbursement_drive = DisbursementDrive.objects.filter(
            team_members=get_current_user(), status=DisbursementDriveStatusEnum.ACTIVE
        ).first()

        connection_disbursement_count = ConnectionDisbursement.objects.filter(
            disbursement_drive=disbursement_drive
        ).exclude(walk_in_date=None).count()

        context.update({
            "current_disbursement_index": connection_disbursement_count,
            "max_walkins": disbursement_drive.max_walk_ins,
            "disbursement_drive": disbursement_drive
        })
        return context


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementMaterialDeliveryView(FormView, ApplicationView):
    model = ConnectionDisbursement
    material_delivery_template = 'ujjwala/disbursement/forms/material_delivery.html'
    material_delivery_qrcode_template = 'ujjwala/disbursement/forms/material_delivery_qrcode.html'
    form_class = ConnectionDisbursementMaterialDeliveryForm
    success_url = '.'

    stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
    stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'

    def dispatch(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_disbursement_drive(user):
            return render(request, 'ujjwala/no_permissions.html')
        connection_disbursement = self.get_object()
        if connection_disbursement:
            if not connection_disbursement.walk_in_date:
                messages.add_message(
                    request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
                        connection_disbursement.parent_id, connection_disbursement.get_status_display()
                    )
                )
                return redirect('ujjwala:connection_disbursement_material_delivery_list')
            if connection_disbursement.status == \
                    ConnectionDisbursementStatusEnum.SV_LABEL_PRINT:


                return self.otp_verification(connection_disbursement)
        return super().dispatch(request, *args, **kwargs)

    def otp_verification(self, connection_disbursement):
        context = {'connection_disbursement': connection_disbursement, 'application': connection_disbursement.parent}

        if self.request.method.lower() == 'get':
            app = connection_disbursement.parent
            context.update({
                'form': UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    initial={
                        'connection_disbursement_id': connection_disbursement.id,
                        'application_id': connection_disbursement.parent_id,
                        'whatsapp_template_name': 'connection_disbursement_dac',
                        'otp_generated_for': f'connectiondisbursement:{connection_disbursement.id}:Material-Delivery',
                    }
                )
            })
            return render(self.request, self.stage_1_generate_otp, context)
        elif self.request.method.lower() == 'post':
            if self.request.POST.get('form_type') == 'generate_otp_form':
                app = UjjwalaV2Application.objects.get(pk=connection_disbursement.parent_id)
                form = UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    data=self.request.POST,
                )
                if not form.is_valid():
                    context.update({
                        'form': form
                    })
                    return render(self.request, self.stage_1_generate_otp, context)
                otp_obj = form.send_otp()
                app_id = form.data.get('application_id')
                context.update({
                    'form': UjjwalaApplicationValidateOtpForm(
                        initial={
                            'application_id': app_id,
                            'reference_number': otp_obj.reference_number,
                            'mobile': otp_obj.mobile
                        }
                    )
                })
                return render(self.request, self.stage_2_validate_otp, context)
            elif self.request.POST.get('form_type') == 'validate_otp_form':
                form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
                otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
                if not form.is_valid():
                    context.update({
                        'form': UjjwalaApplicationValidateOtpForm(
                            initial={
                                'application_id': connection_disbursement.parent_id,
                                'reference_number': otp_obj.reference_number,
                                'mobile': otp_obj.mobile
                            }
                        )
                    })
                    return render(self.request, self.stage_2_validate_otp, context)

                connection_disbursement.transition_material_delivery_otp_verified(
                    by=get_current_user(),
                    description="Material Delivery OTP, Customer Phone {}".format(otp_obj.mobile)
                )
                connection_disbursement.save()
                return HttpResponseRedirect('.')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def get_template_names(self):
        connection_disbursement = self.get_object()
        if connection_disbursement.status == \
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED:
            return self.material_delivery_template
        return self.material_delivery_qrcode_template

    def form_valid(self, form):
        form.save()

        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        connection_disbursement = self.get_object()
        kwargs['connection_disbursement'] = connection_disbursement
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()

        context.update({
            "delivery_type": "First Cylinder Delivery",
            "obj": obj,
        })
        return context


@method_decorator(login_required, 'dispatch')
class InstallationListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        return ConnectionDisbursement.objects.filter(
            status__in=[
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
                ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE,
                ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED,
                ConnectionDisbursementStatusEnum.INSTALLATION_KITCHEN_PHOTO,
                ConnectionDisbursementStatusEnum.FIRST_CYLINDER_DELIVERED,
            ]
        )
        # .filter(
        #     status=PreInspectionStatusEnum.SUBMITTED
        # )

    def get_template_names(self):
        return 'ujjwala/Installation-form/installation_listview.html'

    def get(self, request, *args, **kwargs):
        user = get_current_user()
        if not user.has_perm('ujjwala.can_upload_post_installation'):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            obj = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if obj:
                if not obj.status in (
                        ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
                        ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED,
                        ConnectionDisbursementStatusEnum.FIRST_CYLINDER_DELIVERED,
                        ConnectionDisbursementStatusEnum.INSTALLATION_KITCHEN_PHOTO,
                        ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE,
                ):
                    messages.add_message(
                        request, messages.ERROR, "Application Id {} Application Status: {}".format(
                            obj.parent_id, obj.get_status_display()
                        )
                    )
                    return redirect('ujjwala:installation_list')
                else:
                    return redirect(
                        'ujjwala:installation_form_view',
                        pk=obj.pk
                    )
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)


# @method_decorator(login_required, 'dispatch')
class InstallationView(FormView, ApplicationView):
    model = ConnectionDisbursement
    installation_step1_template = 'ujjwala/Installation-form/steps/step1.html'
    installation_step2_template = 'ujjwala/Installation-form/steps/step2.html'
    success_url = '.'

    stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
    stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'

    def dispatch(self, request, *args, **kwargs):
        # user = get_current_user()
        # if not user.has_perm('ujjwala.can_upload_post_installation'):
        #     return render(request, 'ujjwala/no_permissions.html')

        installation = self.get_object()

        if installation.status in (
                ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
        ):
            return render(self.request, 'ujjwala/Installation-form/installation_status.html', context={
                'installation': installation
            })
        if installation.status in (
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
                ConnectionDisbursementStatusEnum.FIRST_CYLINDER_DELIVERED,
                ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED
        ):
            return self.otp_verification(installation)

        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def get_form_class(self):
        installation_obj = self.get_object()
        if installation_obj.status in (
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
                ConnectionDisbursementStatusEnum.FIRST_CYLINDER_DELIVERED,
                ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED,
                ConnectionDisbursementStatusEnum.INSTALLATION_KITCHEN_PHOTO
        ):
            return InstallationKitchenUploadForm
        elif installation_obj.status == ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE:
            return InstallationMainGateUploadForm

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_template_names(self):
        installation_obj = self.get_object()
        if installation_obj.status in (
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
                ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED,
                ConnectionDisbursementStatusEnum.INSTALLATION_KITCHEN_PHOTO
        ):
            return self.installation_step1_template
        elif installation_obj.status == ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE:
            return self.installation_step2_template

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        installation = self.get_object()
        kwargs['installation'] = installation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = get_current_user()

        if user.is_anonymous:
            installation_mode = "Self-Mode Installation"
        else:
            installation_mode = "Mechanic-Mode Installation By {}".format(user.username)

        context.update({
            "obj": self.get_object(),
            "installation_mode": installation_mode
        })
        return context

    def otp_verification(self, connection_disbursement):
        context = {'connection_disbursement': connection_disbursement, 'application': connection_disbursement.parent}

        if self.request.method.lower() == 'get':
            app = connection_disbursement.parent
            context.update({
                'form': UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    initial={
                        'connection_disbursement_id': connection_disbursement.id,
                        'application_id': connection_disbursement.parent_id,
                        'whatsapp_template_name': 'connection_disbursement_dac',
                        'otp_generated_for': f'connectiondisbursement:{connection_disbursement.id}:Installation',
                    }
                )
            })
            return render(self.request, self.stage_1_generate_otp, context)
        elif self.request.method.lower() == 'post':
            if self.request.POST.get('form_type') == 'generate_otp_form':
                app = UjjwalaV2Application.objects.get(pk=connection_disbursement.parent_id)
                form = UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=app.all_contacts,
                    data=self.request.POST,
                )
                if not form.is_valid():
                    context.update({
                        'form': form
                    })
                    return render(self.request, self.stage_1_generate_otp, context)
                otp_obj = form.send_otp()
                app_id = form.data.get('application_id')
                context.update({
                    'form': UjjwalaApplicationValidateOtpForm(
                        initial={
                            'application_id': app_id,
                            'reference_number': otp_obj.reference_number,
                            'mobile': otp_obj.mobile
                        }
                    )
                })
                return render(self.request, self.stage_2_validate_otp, context)
            elif self.request.POST.get('form_type') == 'validate_otp_form':
                form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
                otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
                if not form.is_valid():
                    context.update({
                        'form': UjjwalaApplicationValidateOtpForm(
                            initial={
                                'application_id': connection_disbursement.parent_id,
                                'reference_number': otp_obj.reference_number,
                                'mobile': otp_obj.mobile
                            }
                        )
                    })
                    return render(self.request, self.stage_2_validate_otp, context)

                connection_disbursement.installation_otp_verified(
                    by=get_current_user(),
                    description="Installation OTP, Customer Phone {}".format(otp_obj.mobile)
                )
                connection_disbursement.save()
                return HttpResponseRedirect('.')


@method_decorator(login_required, 'dispatch')
class InstallationReviewListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 100
    permission = 'has_view_permission'

    def get_queryset(self):
        return ConnectionDisbursement.objects.filter(
            status=ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
        ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/review/installation_review_listview.html'

    def get(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_reviewer_group(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if object:
                if object.status not in (
                        ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
                ):
                    messages.add_message(
                        request, messages.ERROR, "Application Id: {} - {}".format(
                            application_id, object.get_status_display()
                        )
                    )
                else:
                    return redirect('ujjwala:installation_review',
                                    pk=object.pk)
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class InstallationReviewView(FormView, ApplicationView):
    model = ConnectionDisbursement
    template_name = 'ujjwala/review/installation_review.html'
    form_class = InstallationReviewAdminForm

    def get_success_url(self):
        return reverse('ujjwala:installation_review_list')

    def dispatch(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_reviewer_group(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            connection_disbursement = self.get_object()
            if connection_disbursement.status != ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} - {}".format(
                        connection_disbursement.parent_id, connection_disbursement.get_status_display()
                    )
                )
                return redirect('ujjwala:installation_review')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def form_valid(self, form):
        obj = self.get_object()
        data = form.cleaned_data
        obj.transition_installation_reviewed(
            review_status=data['review_status'],
            by=get_current_user(),
            description='{} - {}'.format(data.get('review_status'), data.get('rejected_reason' ''))
        )
        obj.save()
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # connection_disbursement = self.get_object()
        # kwargs['connection_disbursement'] = connection_disbursement
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()

        context.update({
            "obj": obj,
            "kitchen_photo": obj.documents.get(
                type=UjjwalaApplicationDocumentsEnum.INSTALLATION_KITCHEN_PHOTO
            ).link,
            "stove_with_sticker": obj.documents.get(
                type=UjjwalaApplicationDocumentsEnum.INSTALLATION_STOVE_WITH_STICKER
            ).link,
        })
        return context


@method_decorator(login_required, 'dispatch')
class ReviewFormAbcListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 100
    permission = 'has_view_permission'

    def get_queryset(self):
        disbursement_drive = get_current_user_disbursement_drive(get_current_user())
        return ConnectionDisbursement.objects.filter(
            status__in=[
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
            ],
            walk_in_date__date=datetime.datetime.today().date(),
            disbursement_drive=disbursement_drive
        ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/review/review_form_abc_listview.html'

    def get(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_reviewer_group(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if object:
                if object.status not in (
                        ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
                ):
                    messages.add_message(
                        request, messages.ERROR, "Application Id: {} - {}".format(
                            application_id, object.get_status_display()
                        )
                    )
                else:
                    return redirect('ujjwala:connection_disbursement_review_form_abc_view',
                                    pk=object.pk)
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class ReviewFormAbcView(FormView, ApplicationView):
    model = ConnectionDisbursement
    template_name = 'ujjwala/review/review_form_abc.html'
    form_class = LegalDocumentsReviewAdminForm

    def get_success_url(self):
        if '_back_list_view' in self.request.POST:
            return reverse('ujjwala:connection_disbursement_review_form_abc_list')
        if '_next_form_view' in self.request.POST:
            obj = self.get_object()
            return reverse(
                'ujjwala:connection_disbursement_sv_label_print_view',
                kwargs={'pk': obj.pk}
            )
        return '.'

    def dispatch(self, request, *args, **kwargs):
        user = get_current_user()
        if not is_member_of_reviewer_group(user):
            return render(request, 'ujjwala/no_permissions.html')
        application_id = request.GET.get('application_id', '')
        if application_id:
            connection_disbursement = self.get_object()
            if connection_disbursement.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} - {}".format(
                        connection_disbursement.parent_id, connection_disbursement.get_status_display()
                    )
                )
                return redirect('ujjwala:connection_disbursement_review_form_abc_list')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def form_valid(self, form):
        obj = self.get_object()
        data = form.cleaned_data
        obj.transition_legal_documents_reviewed(
            review_status=data['review_status'],
            by=get_current_user(),
            description='{} - {}'.format(data.get('review_status'), data.get('rejected_reason' ''))
        )
        obj.save()
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # connection_disbursement = self.get_object()
        # kwargs['connection_disbursement'] = connection_disbursement
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        form_abc = obj.parent.get_form_abc()
        context.update({
            "obj": obj,
            "form_abc": form_abc
        })
        return context


@method_decorator(login_required, 'dispatch')
class SendInvitationView(FormView):
    # model = ConnectionDisbursementInvitation
    form_class = ConnectionDisbursementInvitationForm
    template_name = "ujjwala/disbursement/send_invitation.html"

    def get_object(self, queryset=None):
        try:
            obj = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No %(verbose_name)s found matching the query" %
                {'verbose_name': queryset.model._meta.verbose_name}
            )
        return obj

    def form_valid(self, form):
        obj = self.get_object()
        form.save(obj)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('admin:ujjwala_connectiondisbursement_change', kwargs={
            'object_id': self.kwargs.get('pk')
        })


@method_decorator(login_required, 'dispatch')
class SetPrimaryPhoneNumberView(FormView):
    form_class = SetPrimaryPhoneNumberForm
    template_name = "ujjwala/application_status/set_primary_number.html"

    def get_object(self, queryset=None):
        try:
            obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No application found with Application Id: {}".format(self.kwargs.get('pk'))
            )
        return obj

    def form_valid(self, form):
        obj = self.get_object()
        data = form.cleaned_data
        obj.uid_linked_mobile = obj.contact_mobile
        obj.contact_mobile = data.get('mobile')
        obj.save()
        return HttpResponse(content="Primary Number Changed Successfully")

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        obj = self.get_object()
        context.update({
            "obj": obj,
        })
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        obj = self.get_object()
        kwargs.update({
            'mobile_nos': obj.all_contacts
        })
        return kwargs


class BarCodeLabelPrintView(View):

    def create_context_data(self, obj: ConnectionDisbursement):
        consumer_no = obj.parent.get_consumer_number()
        context_dict = dict([(f'con_id{index}', val) for index, val in enumerate(consumer_no)])

        address_lines = textwrap.wrap(obj.parent.formatted_address, 63)
        address_lines.extend(['', '', ''])
        address_lines = address_lines[:3]
        context_dict.update(
            dict([(f'address_{index + 1}', val) for index, val in enumerate(address_lines)])
        )

        name = obj.parent.name
        sdms_info = obj.parent.get_sdms_consumer_details()
        if sdms_info:
            if sdms_info.get('contact_name', None):
                name = sdms_info.get('contact_name')

        # contact_name, contact_address
        context_dict.update({
            #"name": sdms_info.get('contact_name', obj.parent.name) if sdms_info else obj.parent.name)
            "name": name,
            "id": obj.parent.id,
            "date": datetime.datetime.today().strftime("%d/%m/%Y")
        })
        return context_dict

    def get(self, request, *args, **kwargs):
        obj = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))

        context = self.create_context_data(obj)
        with open("ujjwala/templates/ujjwala/bluebook_label.prn", "rb") as _fileobj:
            file_data = _fileobj.read()
            for key, value in context.items():
                file_data = file_data.replace(b'{{' + key.encode() + b'}}', str(value).encode())

            # Grab ZIP file from in-memory, make response with correct MIME-type
            resp = HttpResponse(file_data, content_type="application/octet-stream")
            # ..and correct content-disposition
            resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_bluebook_label_{}.prn'.format(
                obj.parent.id)

            return resp


# @method_decorator(login_required, 'dispatch')
class NicErrorUpdateAddress(FormView):
    # model = ConnectionDisbursementInvitation
    form_class = NicUpdateAddressForm
    template_name = "ujjwala/NicErrorUpdateAddress/update_address.html"

    def dispatch(self, request, *args, **kwargs):
        application = self.get_object()
        if application:
            if application.status == \
                    UjjwalaV2ApplicationStatus.NIC_ERROR_UPDATE_ADDRESS:
                return HttpResponse("Address already submitted by you and is under review.")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        try:
            obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No application with id: {} found.".format(self.kwargs.get('pk'))
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context.update({
            "obj": obj
        })
        return context

    def form_valid(self, form):
        obj = self.get_object()
        data = form.clean()
        old_address_json = obj.address_json or obj.address
        obj.transition_nic_address_updated(
            description=old_address_json,
            address_json=data['address_json']
        )
        obj.save()
        return HttpResponse("<b>Address Updated Successfully</b>")


class UpdateAddressView(FormView):
    form_class = UpdateAddressForm
    template_name = "ujjwala/update_address.html"

    def dispatch(self, request, *args, **kwargs):
        application = self.get_object()
        if application:
            if application.address_updated:
                return HttpResponse("Address already submitted by you and is under review.")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        try:
            obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No application with id: {} found.".format(self.kwargs.get('pk'))
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context.update({
            "obj": obj
        })
        return context

    def form_valid(self, form):
        obj = self.get_object()
        data = form.clean()
        old_address_json = obj.address_json or obj.address
        obj.transition_updated_address(
            description=old_address_json,
            address_json=data['address_json']
        )
        obj.save()
        return HttpResponse("<b>Address Updated Successfully</b>")


class PreInspectionConvertToView(FormView):
    # model = ConnectionDisbursementInvitation
    form_class = PreInspectionConvertForm
    template_name = "ujjwala/pre-inspection/pre_inspection_conversion.html"

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj:
            if obj.status in (
                    PreInspectionStatusEnum.SUBMITTED,
                    PreInspectionStatusEnum.ACCEPTED,
            ):
                return HttpResponse("Pre Inspection Already Submitted")
            if self.kwargs.get('convert_to') == 'mech' and obj.type == PreInspectionTypeEnum.MECHANIC:
                return redirect(
                    reverse('ujjwala:pre_inspection_form_view',
                            args=('mech', obj.pk)) + '?{}'.format(request.GET.urlencode())
                )
                # return redirect('ujjwala:pre_inspection_form_view', type="mech", pk=obj.pk)
            elif self.kwargs.get('convert_to') == 'self' and obj.type == PreInspectionTypeEnum.SELF:
                return redirect(
                    reverse('ujjwala:pre_inspection_form_view',
                            args=('self', obj.pk)) + '?{}'.format(request.GET.urlencode())
                )
                # return redirect('ujjwala:pre_inspection_form_view', type="self", pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        try:
            obj = PreInspection.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No application with id: {} found.".format(self.kwargs.get('pk'))
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        convert_to = self.kwargs.get('convert_to')
        context.update({
            "obj": obj,
            "convert_to": PreInspectionTypeEnum.MECHANIC if convert_to == 'mech' else PreInspectionTypeEnum.SELF
        })
        return context

    def get_initial(self):
        kwargs = super().get_initial()
        kwargs.update({
            'convert_to': self.kwargs.get('convert_to')
        })
        return kwargs

    def form_valid(self, form):
        obj = self.get_object()
        data = form.clean()

        if data['convert_to'] == 'mech':
            convert_to = PreInspectionTypeEnum.MECHANIC
        else:
            convert_to = PreInspectionTypeEnum.SELF

        if not obj.type == convert_to:
            obj.convert_inspection_type(convert_to_type=data['convert_to'])
            obj.save()
        return redirect(
            reverse('ujjwala:pre_inspection_form_view',
                    args=(data['convert_to'], obj.pk)) + '?{}'.format(self.request.GET.urlencode())
        )
        # return redirect('ujjwala:pre_inspection_form_view', type=data['convert_to'], pk=obj.pk)


@method_decorator(login_required, 'dispatch')
class UjjwalaPreInspectionUserListView(ListView):
    model = PreInspection
    template_name = 'ujjwala/pre-inspection/pre_inspection_user_listview.html'
    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        return PreInspection.objects.filter(
            mechanic=get_current_user()
        ).order_by('-submitted_on')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        list_pre_inspection = PreInspection.objects.filter(mechanic=get_current_user())
        paginator = Paginator(list_pre_inspection, self.paginate_by)

        page = self.request.GET.get('page')

        try:
            list_pre_inspection = paginator.page(page)
        except PageNotAnInteger:
            list_pre_inspection = paginator.page(1)
        except EmptyPage:
            list_pre_inspection = paginator.page(paginator.num_pages)

        context['list_pre_inspection'] = list_pre_inspection
        return context


class UpdateBankDetailsFormView(FormView):
    form_class = UpdateBankDetailsForm

    def get_template_names(self):
        obj = self.get_object()
        if obj.ifsc_code:
            return "ujjwala/extra/show_bank_details.html"
        else:
            return "ujjwala/extra/update_bank_details.html"

    def get_object(self, queryset=None):
        try:
            obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No application found with Application Id: {}".format(self.kwargs.get('pk'))
            )
        return obj

    def form_valid(self, form):
        form.save()

        obj = self.get_object()
        messages.add_message(
            self.request, messages.INFO, "Application Id {}: Remarks Updated: {}".format(obj.pk, obj.customer_remarks)
        )
        return redirect('ujjwala:application_status_search')

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        obj = self.get_object()
        context.update({
            "obj": obj,
        })
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        obj = self.get_object()
        kwargs.update({
            'application': obj
        })
        return kwargs


class NicClearedCustomerRemarks(FormView):
    form_class = NicClearedCustomerRemarksForm
    template_name = "ujjwala/extra/nic_cleared_customer_remarks.html"

    def get_object(self, queryset=None):
        try:
            obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No application found with Application Id: {}".format(self.kwargs.get('pk'))
            )
        return obj

    def form_valid(self, form):
        data = form.cleaned_data
        obj = self.get_object()
        obj.customer_remarks = data['customer_remarks']
        obj.availability_status = data['customer_remarks']
        obj.availability_channel = UjjwalaV2ApplicationAvailabilityChannel.USER
        obj.availability_updated_on = datetime.datetime.now()
        obj.scheduled_date = data['scheduled_date']
        obj.additional_remarks = data['description']
        obj.save()
        messages.add_message(
            self.request, messages.INFO, "Application Id {}: Remarks Updated: {}".format(obj.pk, obj.customer_remarks)
        )
        return redirect('ujjwala:application_status_search')
        #
        # return HttpResponse(content="Customer Remarks Updated Successfully.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        obj = self.get_object()
        context.update({"obj": obj, })
        return context


class PrintDocumentsView(FormView):
    form_class = PrintDocumentsForm
    template_name = "ujjwala/extra/print_documents.html"

    # def get_object(self, queryset=None):
    #     try:
    #         obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
    #     except:
    #         raise Http404(
    #             "No application found with Application Id: {}".format(self.kwargs.get('pk'))
    #         )
    #     return obj

    def form_valid(self, form):
        data = form.cleaned_data
        res = download_audit_documents_for_ids(data['ids'], data['documents'],)

        # django_rq.enqueue(
        #     download_audit_documents_for_ids,
        #     args=(data['ids'], data['documents'],),
        #     result_ttl=86400 * 2
        # )
        # return HttpResponse(content=res)
        return res


# @method_decorator(login_required, 'dispatch')
# class FirstCylinderMaterialDeliveryListView(ListView):
#     model = ConnectionDisbursement
#
#     paginate_by = 20
#     permission = 'has_view_permission'
#
#     def get_queryset(self):
#         disbursement_drive = get_current_user_disbursement_drive(get_current_user())
#         return ConnectionDisbursement.objects.filter(
#             status__in=[
#                 ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
#                 ConnectionDisbursementStatusEnum.FIRST_DELIVERY_OTP_VERIFIED,
#             ],
#             walk_in_date__date=datetime.datetime.today().date(),
#             disbursement_drive=disbursement_drive
#         ).order_by('updated_on')
#
#     def get_template_names(self):
#         return 'ujjwala/delivery/first_delivery/first_cylinder_delivery_listview.html'
#
#     def get(self, request, *args, **kwargs):
#         user = get_current_user()
#         if not is_member_of_disbursement_drive(user):
#             return render(request, 'ujjwala/no_permissions.html')
#         application_id = request.GET.get('application_id', '')
#         if application_id:
#             object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
#             if object:
#                 if not object.walk_in_date:
#                     messages.add_message(
#                         request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
#                             object.parent_id, object.get_status_display()
#                         )
#                     )
#                     return redirect('ujjwala:first_cylinder_delivery_list')
#                 if object.status not in (
#                         ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
#                         ConnectionDisbursementStatusEnum.FIRST_CYLINDER_DELIVERED,
#                         ConnectionDisbursementStatusEnum.FIRST_DELIVERY_OTP_VERIFIED,
#
#                 ):
#                     messages.add_message(
#                         request, messages.ERROR, "Application Id: {} - {}".format(
#                             application_id, object.get_status_display()
#                         )
#                     )
#                 else:
#                     return redirect('ujjwala:first_cylinder_delivery_view',
#                                     pk=object.pk
#                                     )
#             else:
#                 messages.add_message(
#                     request, messages.ERROR, "Application Id: {} not found".format(application_id)
#                 )
#         return super().get(request, *args, **kwargs)
#
#     def get_context_data(self, *, object_list=None, **kwargs):
#         context = super().get_context_data(object_list=object_list, **kwargs)
#         disbursement_drive = DisbursementDrive.objects.filter(
#             team_members=get_current_user(), status=DisbursementDriveStatusEnum.ACTIVE
#         ).first()
#
#         connection_disbursement_count = ConnectionDisbursement.objects.filter(
#             disbursement_drive=disbursement_drive
#         ).exclude(walk_in_date=None).count()
#
#         context.update({
#             "current_disbursement_index": connection_disbursement_count,
#             "max_walkins": disbursement_drive.max_walk_ins,
#             "disbursement_drive": disbursement_drive
#         })
#         return context
#
#
# @method_decorator(login_required, 'dispatch')
# class FirstCylinderMaterialDeliveryView(FormView, ApplicationView):
#     model = ConnectionDisbursement
#     material_delivery_template = 'ujjwala/delivery/first_delivery/first_cylinder_delivery.html'
#     material_delivery_qrcode_template = 'ujjwala/delivery/first_delivery/material_delivery_qrcode.html'
#     form_class = FirstCylinderMaterialDeliveryForm
#     success_url = '.'
#
#     stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
#     stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'
#
#     def dispatch(self, request, *args, **kwargs):
#         user = get_current_user()
#         if not is_member_of_disbursement_drive(user):
#             return render(request, 'ujjwala/no_permissions.html')
#         connection_disbursement = self.get_object()
#         if connection_disbursement:
#             if not connection_disbursement.walk_in_date:
#                 messages.add_message(
#                     request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
#                         connection_disbursement.parent_id, connection_disbursement.get_status_display()
#                     )
#                 )
#                 return redirect('ujjwala:first_cylinder_delivery_list')
#             if connection_disbursement.status == \
#                     ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES:
#                 return self.otp_verification(connection_disbursement)
#         return super().dispatch(request, *args, **kwargs)
#
#     def otp_verification(self, connection_disbursement):
#         context = {'connection_disbursement': connection_disbursement, 'application': connection_disbursement.parent}
#
#         if self.request.method.lower() == 'get':
#             app = connection_disbursement.parent
#             context.update({
#                 'form': UjjwalaApplicationGenerateOtpForm(
#                     mobile_nos=app.all_contacts,
#                     initial={
#                         'connection_disbursement_id': connection_disbursement.id,
#                         'application_id': connection_disbursement.parent_id,
#                         'whatsapp_template_name': 'connection_disbursement_dac',
#                         'otp_generated_for': f'connectiondisbursement:{connection_disbursement.id}:Material-Delivery',
#                     }
#                 )
#             })
#             return render(self.request, self.stage_1_generate_otp, context)
#         elif self.request.method.lower() == 'post':
#             if self.request.POST.get('form_type') == 'generate_otp_form':
#                 app = UjjwalaV2Application.objects.get(pk=connection_disbursement.parent_id)
#                 form = UjjwalaApplicationGenerateOtpForm(
#                     mobile_nos=app.all_contacts,
#                     data=self.request.POST,
#                 )
#                 if not form.is_valid():
#                     context.update({
#                         'form': form
#                     })
#                     return render(self.request, self.stage_1_generate_otp, context)
#                 otp_obj = form.send_otp()
#                 app_id = form.data.get('application_id')
#                 context.update({
#                     'form': UjjwalaApplicationValidateOtpForm(
#                         initial={
#                             'application_id': app_id,
#                             'reference_number': otp_obj.reference_number,
#                             'mobile': otp_obj.mobile
#                         }
#                     )
#                 })
#                 return render(self.request, self.stage_2_validate_otp, context)
#             elif self.request.POST.get('form_type') == 'validate_otp_form':
#                 form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
#                 otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
#                 if not form.is_valid():
#                     context.update({
#                         'form': UjjwalaApplicationValidateOtpForm(
#                             initial={
#                                 'application_id': connection_disbursement.parent_id,
#                                 'reference_number': otp_obj.reference_number,
#                                 'mobile': otp_obj.mobile
#                             }
#                         )
#                     })
#                     return render(self.request, self.stage_2_validate_otp, context)
#
#                 connection_disbursement.transition_first_cylinder_delivery_otp_verified(
#                     by=get_current_user(),
#                     description="First Cylinder Material Delivery OTP, Customer Phone {}".format(otp_obj.mobile)
#                 )
#                 connection_disbursement.save()
#                 return HttpResponseRedirect('.')
#
#     def get_object(self, queryset=None):
#         obj = super().get_object(queryset=queryset)
#         return obj
#
#     def get_template_names(self):
#         connection_disbursement = self.get_object()
#         if connection_disbursement.status == \
#                 ConnectionDisbursementStatusEnum.FIRST_DELIVERY_OTP_VERIFIED:
#             return self.material_delivery_template
#         return self.material_delivery_qrcode_template
#
#     def form_valid(self, form):
#         form.save()
#         return HttpResponseRedirect(self.get_success_url())
#
#     def get_form_kwargs(self):
#         kwargs = super().get_form_kwargs()
#         connection_disbursement = self.get_object()
#         kwargs['connection_disbursement'] = connection_disbursement
#         return kwargs
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         obj = self.get_object()
#
#         context.update({
#             "obj": obj,
#         })
#         return context
#
#
# @method_decorator(login_required, 'dispatch')
# class SecondCylinderMaterialDeliveryListView(ListView):
#     model = ConnectionDisbursement
#
#     paginate_by = 20
#     permission = 'has_view_permission'
#
#     def get_queryset(self):
#         return ConnectionDisbursement.objects.filter(
#             status__in=[
#                 ConnectionDisbursementStatusEnum.INSTALLATION_ACCEPTED,
#                 ConnectionDisbursementStatusEnum.SECOND_DELIVERY_OTP_VERIFIED,
#             ], pending_quantity=1
#         ).order_by('updated_on')
#
#     def get_template_names(self):
#         return 'ujjwala/delivery/second_delivery/second_cylinder_delivery_listview.html'
#
#     def get(self, request, *args, **kwargs):
#         user = get_current_user()
#         if not is_member_of_second_cylinder_delivery(user):
#             return render(request, 'ujjwala/no_permissions.html')
#         application_id = request.GET.get('application_id', '')
#         if application_id:
#             object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
#             if object:
#                 if not object.walk_in_date:
#                     messages.add_message(
#                         request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
#                             object.parent_id, object.get_status_display()
#                         )
#                     )
#                     return redirect('ujjwala:second_cylinder_delivery_list')
#                 if object.status not in (
#                         ConnectionDisbursementStatusEnum.SECOND_DELIVERY_OTP_VERIFIED,
#                 ):
#                     messages.add_message(
#                         request, messages.ERROR, "Application Id: {} - {}".format(
#                             application_id, object.get_status_display()
#                         )
#                     )
#                 else:
#                     return redirect('ujjwala:second_cylinder_delivery_view',
#                                     pk=object.pk
#                                     )
#             else:
#                 messages.add_message(
#                     request, messages.ERROR, "Application Id: {} not found".format(application_id)
#                 )
#         return super().get(request, *args, **kwargs)
#
#
# @method_decorator(login_required, 'dispatch')
# class SecondCylinderMaterialDeliveryView(FormView, ApplicationView):
#     model = ConnectionDisbursement
#     material_delivery_template = 'ujjwala/delivery/second_delivery/second_cylinder_delivery.html'
#     form_class = SecondCylinderMaterialDeliveryForm
#     success_url = '.'
#
#     stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
#     stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'
#
#     def dispatch(self, request, *args, **kwargs):
#         user = get_current_user()
#         if not is_member_of_second_cylinder_delivery(user):
#             return render(request, 'ujjwala/no_permissions.html')
#         connection_disbursement = self.get_object()
#         if connection_disbursement:
#             if connection_disbursement.pending_quantity == 0:
#                 return HttpResponse(content="<h1>No Cylinder Pending</h1>")
#             if not connection_disbursement.status in (
#                     ConnectionDisbursementStatusEnum.INSTALLATION_ACCEPTED,
#                     ConnectionDisbursementStatusEnum.SECOND_DELIVERY_OTP_VERIFIED,
#             ):
#                 messages.add_message(
#                     request, messages.ERROR,
#                     "Application Id {} Installation Not Accepted. Application Status: {}".format(
#                         connection_disbursement.parent_id, connection_disbursement.get_status_display()
#                     )
#                 )
#                 return redirect('ujjwala:second_cylinder_delivery_list')
#             if connection_disbursement.status == ConnectionDisbursementStatusEnum.INSTALLATION_ACCEPTED:
#                 return self.otp_verification(connection_disbursement)
#         return super().dispatch(request, *args, **kwargs)
#
#     def otp_verification(self, connection_disbursement):
#         context = {'connection_disbursement': connection_disbursement, 'application': connection_disbursement.parent}
#
#         if self.request.method.lower() == 'get':
#             app = connection_disbursement.parent
#             context.update({
#                 'form': UjjwalaApplicationGenerateOtpForm(
#                     mobile_nos=app.all_contacts,
#                     initial={
#                         'connection_disbursement_id': connection_disbursement.id,
#                         'application_id': connection_disbursement.parent_id,
#                         'whatsapp_template_name': 'connection_disbursement_dac',
#                         'otp_generated_for': f'connectiondisbursement:{connection_disbursement.id}:Second-Cylinder-Delivery',
#                     }
#                 )
#             })
#             return render(self.request, self.stage_1_generate_otp, context)
#         elif self.request.method.lower() == 'post':
#             if self.request.POST.get('form_type') == 'generate_otp_form':
#                 app = UjjwalaV2Application.objects.get(pk=connection_disbursement.parent_id)
#                 form = UjjwalaApplicationGenerateOtpForm(
#                     mobile_nos=app.all_contacts,
#                     data=self.request.POST,
#                 )
#                 if not form.is_valid():
#                     context.update({
#                         'form': form
#                     })
#                     return render(self.request, self.stage_1_generate_otp, context)
#                 otp_obj = form.send_otp()
#                 app_id = form.data.get('application_id')
#                 context.update({
#                     'form': UjjwalaApplicationValidateOtpForm(
#                         initial={
#                             'application_id': app_id,
#                             'reference_number': otp_obj.reference_number,
#                             'mobile': otp_obj.mobile
#                         }
#                     )
#                 })
#                 return render(self.request, self.stage_2_validate_otp, context)
#             elif self.request.POST.get('form_type') == 'validate_otp_form':
#                 form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
#                 otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
#                 if not form.is_valid():
#                     context.update({
#                         'form': UjjwalaApplicationValidateOtpForm(
#                             initial={
#                                 'application_id': connection_disbursement.parent_id,
#                                 'reference_number': otp_obj.reference_number,
#                                 'mobile': otp_obj.mobile
#                             }
#                         )
#                     })
#                     return render(self.request, self.stage_2_validate_otp, context)
#
#                 connection_disbursement.transition_second_delivery_otp_verified(
#                     by=get_current_user(),
#                     description="Second Material Delivery OTP, Customer Phone: {}".format(otp_obj.mobile)
#                 )
#                 connection_disbursement.save()
#                 return HttpResponseRedirect('.')
#
#     def get_object(self, queryset=None):
#         obj = super().get_object(queryset=queryset)
#         return obj
#
#     def get_template_names(self):
#         connection_disbursement = self.get_object()
#         if connection_disbursement.status == \
#                 ConnectionDisbursementStatusEnum.SECOND_DELIVERY_OTP_VERIFIED:
#             return self.material_delivery_template
#         return self.material_delivery_qrcode_template
#
#     def form_valid(self, form):
#         form.save()
#         return HttpResponseRedirect(self.get_success_url())
#
#     def get_form_kwargs(self):
#         kwargs = super().get_form_kwargs()
#         connection_disbursement = self.get_object()
#         kwargs['connection_disbursement'] = connection_disbursement
#         return kwargs
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         obj = self.get_object()
#         context.update({
#             "obj": obj
#         })
#         return context

class LegalDocumentsAcceptedToPendingView(View):

    def dispatch(self, request, *args, **kwargs):
        connection_disbursement = ConnectionDisbursement.objects.get(parent_id=kwargs.get('pk'))
        connection_disbursement.transition_legal_documents_pending(data={'reason': 'LOST'})
        connection_disbursement.save()

        return JsonResponse({
            "status": "Updated"
        })


class ShareOnSocialMediaView(View):
    def get(self, request, *args, **kwargs):
        connection_disbursement_id = kwargs.get('pk', '')

        if not connection_disbursement_id:
            return render(
                self.request, "ujjwala/response.html",
                {"heading": "Share On Social Media", "message": "Invalid Link"}
            )

        connection_disbursement = ConnectionDisbursement.objects.get(pk=connection_disbursement_id)

        if connection_disbursement.social_media_update_done:
            return render(
                self.request, "ujjwala_share/ujjwala.html",
                {
                    "name": connection_disbursement.parent.name,
                    "social_media_url": connection_disbursement.documents.filter(
                        type=UjjwalaApplicationDocumentsEnum.SOCIAL_MEDIA_PHOTO).first().link
                }
            )
        else:
            return render(
                self.request, "ujjwala/response.html",
                {"heading": "Share On Social Media", "message": "Social Media Photo Not Uploaded"}
            )


# @method_decorator(login_required, 'dispatch')
class CancelInvitationView(FormView):
    form_class = CancelInvitationForm
    template_name = "ujjwala/disbursement/cancel_invitation.html"

    def get_object(self, queryset=None):
        try:
            obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No application with id: {} found.".format(self.kwargs.get('pk'))
            )
        return obj


    def form_valid(self, form):
        data = form.clean()
        obj = UjjwalaV2Application.objects.filter(id=data['application_id']).first()
        if not obj:
            messages.add_message(self.request, messages.ERROR,
                                 "No Application Exist With Given Id: {}".format(data['application_id']))
            return redirect(".")

        invitation = obj.connection_disbursement.invitation.filter(status=ConnectionDisbursementInvitationEnum.VALID)
        if not invitation.exists():
            messages.add_message(self.request, messages.ERROR,
                                 "No Invitation Exist For Given Application Id: {}".format(data['application_id']))
            return redirect(".")

        invitation = invitation.first()
        invitation.status = ConnectionDisbursementInvitationEnum.CANCELED
        invitation.canceled_reason = data['reason']
        invitation.save()
        messages.add_message(self.request, messages.ERROR, "Invitation Canceled")
        return redirect(".")


# @method_decorator(login_required, 'dispatch')
class UpdateRelationshipNumberView(FormView):
    form_class = NewRelationCreated
    template_name = "ujjwala/extra/update_relationship_number.html"

    def get_object(self, queryset=None):
        try:
            obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No application with id: {} found.".format(self.kwargs.get('pk'))
            )
        return obj


    def form_valid(self, form):
        data = form.clean()
        application = self.get_object()
        application.consumer_id = data['consumer_id']
        application.save()
        messages.add_message(self.request, messages.INFO, "New Consumer Id Updated")
        return redirect(".")

