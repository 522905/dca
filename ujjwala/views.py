import datetime
import json
import re
import textwrap

import django_rq
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.template import loader
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django_currentuser.middleware import get_current_user
from django.forms import formset_factory


import ujjwala.forms
from otp.models import Otp
from ujjwala.enums import UjjwalaV2ApplicationStatus, PreInspectionStatusEnum, ConnectionDisbursementStatusEnum, \
    PreInspectionTypeEnum
from ujjwala.forms import UjjwalaDocumentsReuploadForm, PreInspectionInitialForm, \
    PreInspectionGenerateOtpForm, PreInspectionValidateOtpForm, \
    KitchenPreInspectionForm, AudioOnSafetyForm, PreviewPreInspectionForm, PreInspectionAllocatedGenerateOtpForm, \
    PreInspectionAllocatedValidateOtpForm, UjjwalaLegalDocumentsUpload, ChangeAddressForm, \
    ConnectionDisbursementSvLabelPrintForm, InstallationMainGateUploadForm, InstallationKitchenUploadForm, \
    UjjwalaApplicationOtpInitialForm, UjjwalaApplicationGenerateOtpForm, UjjwalaApplicationValidateOtpForm, \
    ConnectionDisbursementMaterialDeliveryForm, ConnectionDisbursementInvitationForm, \
    ConnectionDisbursementSocialMediaUpdatesForm, ConnectionDisbursementSearchForm, NicUpdateAddressForm, \
    PreInspectionConvertForm
from ujjwala.global_functions import login_required_if_mech_inspection

from ujjwala.models import UjjwalaV2Application, PreInspection, ConnectionDisbursement, ConnectionDisbursementInvitation


def index(request):
    return render(request, 'ujjwala/index.html')


def legal_documents(request):
    return render(request, 'ujjwala/legal_documents_upload.html')


class WhatsappNicErrorUpdateAddress(View):
    def get(self, request, *args, **kwargs):
        obj = UjjwalaV2Application.objects.filter(pk=kwargs.get('pk')).first()
        if obj:
            obj.event_whatsapp_nic_error_update_address()
            return HttpResponse("Application Id {}: Message Sent".format(kwargs.get('pk')))
        return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))


class WhatsappPreInspectionTypeSelf(View):
    def get(self, request, *args, **kwargs):
        application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()
        if not application:
            return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))

        pi_obj = PreInspection.objects.filter(parent_id=kwargs.get('pk')).first()
        # obj = UjjwalaV2Application.objects.filter(pk=kwargs.get('pk')).first()
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


class ApplicationStatusView(DetailView):
    model = UjjwalaV2Application

    def get_template_names(self):
        return 'ujjwala/status.html'


@method_decorator(login_required, 'dispatch')
class UjjwalaPreInspectionListView(ListView):
    model = PreInspection

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        return PreInspection.objects.filter(
            mechanic=get_current_user()
        )

    def get_template_names(self):
        return 'ujjwala/pre_inspection_listview.html'


@method_decorator(login_required, 'dispatch')
class UjjwalaPreInspectionReviewListView(ListView):
    model = PreInspection

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        return PreInspection.objects.filter(
            status=PreInspectionStatusEnum.SUBMITTED
        )

    def get_template_names(self):
        return 'ujjwala/pre_inspection_review_listview.html'


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationReuploadView(DetailView):
    model = UjjwalaV2Application

    def get_template_names(self):
        return 'ujjwala/ujjwala_documents_reupload.html'


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


@method_decorator(login_required, 'dispatch')
class InstallationView(FormView):
    model = ConnectionDisbursement
    installation_step1_template = 'ujjwala/Installation-form/steps/step1.html'
    installation_step2_template = 'ujjwala/Installation-form/steps/step2.html'
    success_url = '.'

    def dispatch(self, request, *args, **kwargs):
        installation = self.get_object()
        if installation.status in (
                ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
        ):
            return render(self.request, 'ujjwala/installation_status.html', context={
                'installation': installation
            })
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        try:
            obj = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No %(verbose_name)s found matching the query" %
                  {'verbose_name': queryset.model._meta.verbose_name}
            )
        return obj

    def get_form_class(self):
        installation_obj = self.get_object()
        if installation_obj.status == ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED:
            return InstallationKitchenUploadForm
        elif installation_obj.status == ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE:
            return InstallationMainGateUploadForm

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_template_names(self):
        installation_obj = self.get_object()
        if installation_obj.status == ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED:
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
        context.update({
            "obj": self.get_object()
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
                ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE
            ]
        )
        # .filter(
        #     status=PreInspectionStatusEnum.SUBMITTED
        # )

    def get_template_names(self):
        return 'ujjwala/installation_listview.html'


@method_decorator(login_required_if_mech_inspection, 'dispatch')
class PreInspectionView(FormView):
    model = PreInspection
    pre_inspection_step0_template = 'ujjwala/pre-Inspection-form/steps/step0.html'
    pre_inspection_step1_template = 'ujjwala/pre-Inspection-form/steps/step1.html'
    pre_inspection_step2_template = 'ujjwala/pre-Inspection-form/steps/step2.html'
    pre_inspection_step3_template = 'ujjwala/pre-Inspection-form/steps/step3.html'
    success_url = '.'

    stage_1_generate_otp = 'ujjwala/pre_inspection_generate_otp_form.html'
    stage_2_validate_otp = 'ujjwala/pre_inspection_validate_otp_form.html'

    def dispatch(self, request, *args, **kwargs):
        pre_inspection = PreInspection.objects.get(pk=kwargs.get('pk'))

        if pre_inspection.status in (
                PreInspectionStatusEnum.ALLOCATED,
                PreInspectionStatusEnum.REJECTED
        ):
            return self.otp_verification(pre_inspection)
        elif pre_inspection.status in (
                PreInspectionStatusEnum.SUBMITTED,
                PreInspectionStatusEnum.ACCEPTED,
        ):
            return render(self.request, 'ujjwala/pre_inspection_status.html', context={
                'pre_inspection': pre_inspection
            })
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
        elif application.status == PreInspectionStatusEnum.KITCHEN_PHOTO:
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
                return HttpResponse(
                    content="<h1>Pre-Inspection Submitted For Review</h1>"
                )
        return HttpResponseRedirect(self.get_success_url())

    def get_template_names(self):
        pre_inspection_obj = self.get_object()
        if pre_inspection_obj.status == PreInspectionStatusEnum.CHANGE_ADDRESS:
            return self.pre_inspection_step0_template
        elif pre_inspection_obj.status == PreInspectionStatusEnum.KITCHEN_PHOTO:
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
        context.update({
            "obj": self.get_object()
        })
        return context


@method_decorator(login_required, 'dispatch')
class PreInspectionCreateView(View):
    model = PreInspection
    stage_1_template = 'ujjwala/pre_inspection_initial_form.html'
    stage_2_template = 'ujjwala/pre_inspection_generate_otp_form.html'
    stage_3_template = 'ujjwala/pre_inspection_validate_otp_form.html'

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


class PreInspectionReviewView(FormView):
    template_name = "ujjwala/pre_inspection_review.html"

    def get_form_class(self):
        return formset_factory(ReviewForm, extra=0)

    def get_initial(self):
        return [
            {
                'pre_inspection_id': obj.id
            } for obj in PreInspection.objects.all()
        ]


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


# Class For Getting Application Object
@method_decorator(login_required, 'dispatch')
class ApplicationView(View):

    def get_object(self, queryset=None):
        try:
            obj = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))
        except:
            raise Http404(
                "No Application Exist For Given Application Id"
            )
        return obj


@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 100
    permission = 'has_view_permission'

    def get_queryset(self):
        return ConnectionDisbursement.objects.filter(
            status__in=[
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED
            ],
            walk_in_date__date=datetime.datetime.today().date()
        ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/connection_disbursement_listview.html'

    def get(self, request, *args, **kwargs):
        application_id = request.GET.get('application_id', '')
        if application_id:
            object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if object:
                if object.status not in (
                    ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
                    ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
                    ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED
                ):
                    messages.add_message(
                        request, messages.ERROR, "Application Id: {} - {}".format(application_id, object.status)
                    )
                else:
                    return redirect('ujjwala:connection_disbursement_form_view',
                                    pk=object.pk
                                    )
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementView(TemplateView, ApplicationView):
    model = ConnectionDisbursement
    walk_in_template = 'ujjwala/connection-disbursement/forms/walk_in_confirmation.html'
    ujjwala_form_a_b_c_template = "ujjwala/connection-disbursement/print_ujjwala_form_a_b_c.html"
    success_url = '.'

    stage_1_generate_otp = 'ujjwala/generate_otp_form.html'
    stage_2_validate_otp = 'ujjwala/validate_otp_form.html'

    def dispatch(self, request, *args, **kwargs):
        connection_disbursement = self.get_object()
        if connection_disbursement:
            if not connection_disbursement.walk_in_date or \
                    (connection_disbursement.walk_in_date.date() != datetime.datetime.today().date()):
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
                        'otp_generated_for': 'WalkInConfirmation',
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

                connection_disbursement.walk_in_date = datetime.datetime.now()
                connection_disbursement.save()
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


# Step - 2 SV Label Print List View & Form View
@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementSvLabelPrintListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        return ConnectionDisbursement.objects.filter(
            status__in=[
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
            ],
            walk_in_date__date=datetime.datetime.today().date()
        ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/connection-disbursement/forms/connection_disbursement_sv_label_print_listview.html'

    def get(self, request, *args, **kwargs):
        application_id = request.GET.get('application_id', '')
        if application_id:
            object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if object:
                if object.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED:
                    messages.add_message(
                        request, messages.ERROR, "Application Id: {} - {}".format(application_id, object.status)
                    )
                else:
                    return redirect('ujjwala:connection_disbursement_sv_label_print_view',
                                    pk=object.pk
                                    )
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementSvLabelPrintView(FormView, ApplicationView):
    model = ConnectionDisbursement
    template_name = 'ujjwala/connection-disbursement/forms/sv_label_print.html'
    form_class = ConnectionDisbursementSvLabelPrintForm
    success_url = '.'


    def dispatch(self, request, *args, **kwargs):
        application_id = request.GET.get('application_id', '')
        if application_id:
            connection_disbursement = self.get_object()
            if connection_disbursement.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} - {}".format(
                        connection_disbursement.parent_id, connection_disbursement.status
                    )
                )
                return redirect('ujjwala:connection_disbursement_sv_label_print_list')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def form_valid(self, form):
        form.save()
        return redirect('ujjwala:connection_disbursement_sv_label_print_list')

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
            kwargs={'pk':obj.id}
        )
        context.update({
            "obj": obj,
            "bluebook_label_print_url": self.request.build_absolute_uri(bluebook_label_print_url)
        })
        return context


# Step - 3 Social Media Updates List View & Form View
@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementSocialMediaUpdatesListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        return ConnectionDisbursement.objects.filter(
            status__in=[
                ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
            ],
            walk_in_date__date=datetime.datetime.today().date()
        ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/connection-disbursement/forms/connection_disbursement_social_media_updates_listview.html'

    def get(self, request, *args, **kwargs):
        application_id = request.GET.get('application_id', '')
        if application_id:
            object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if object:
                if object.status != ConnectionDisbursementStatusEnum.SV_LABEL_PRINT:
                    messages.add_message(
                        request, messages.ERROR, "Application Id: {} - {}".format(application_id, object.status)
                    )
                else:
                    return redirect('ujjwala:connection_disbursement_social_media_updates_view',
                                    pk=object.pk
                                    )
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementSocialMediaUpdatesView(FormView, ApplicationView):
    model = ConnectionDisbursement
    template_name = 'ujjwala/connection-disbursement/forms/social_media_updates.html'
    form_class = ConnectionDisbursementSocialMediaUpdatesForm
    success_url = '.'

    def dispatch(self, request, *args, **kwargs):
        application_id = request.GET.get('application_id', '')
        if application_id:
            connection_disbursement = self.get_object()
            if connection_disbursement.status != ConnectionDisbursementStatusEnum.SV_LABEL_PRINT:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} - {}".format(
                        connection_disbursement.parent_id, connection_disbursement.status
                    )
                )
                return redirect('ujjwala:connection_disbursement_social_media_updates_list')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def form_valid(self, form):
        form.save()
        return redirect('ujjwala:connection_disbursement_social_media_updates_list')

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
        return ConnectionDisbursement.objects.filter(
            status__in=[
                ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
                ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
            ],
            walk_in_date__date=datetime.datetime.today().date()
        ).order_by('updated_on')

    def get_template_names(self):
        return 'ujjwala/connection-disbursement/forms/connection_disbursement_material_delivery_listview.html'

    def get(self, request, *args, **kwargs):
        application_id = request.GET.get('application_id', '')
        if application_id:
            object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
            if object:
                if object.status not in (
                        ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
                        ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
                        ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED
                ):
                    messages.add_message(
                        request, messages.ERROR, "Application Id: {} - {}".format(application_id, object.status)
                    )
                else:
                    return redirect('ujjwala:connection_disbursement_material_delivery_view',
                                    pk=object.pk
                                )
            else:
                messages.add_message(
                    request, messages.ERROR, "Application Id: {} not found".format(application_id)
                )
        return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementMaterialDeliveryView(FormView, ApplicationView):
    model = ConnectionDisbursement
    material_delivery_template = 'ujjwala/connection-disbursement/forms/material_delivery.html'
    material_delivery_qrcode_template = 'ujjwala/connection-disbursement/forms/material_delivery_qrcode.html'
    form_class = ConnectionDisbursementMaterialDeliveryForm
    success_url = '.'

    stage_1_generate_otp = 'ujjwala/generate_otp_form.html'
    stage_2_validate_otp = 'ujjwala/validate_otp_form.html'

    def dispatch(self, request, *args, **kwargs):
        connection_disbursement = self.get_object()
        if connection_disbursement:
            if connection_disbursement.status == \
                    ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES:
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
                        'otp_generated_for': 'MaterialDelivery',
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
        invitation = obj.invitation.first()
        if invitation:
           booking_id =  obj.invitation.first().booking_id
        else:
           booking_id = ''
        context.update({
            "obj": obj,
            "booking_id": booking_id
        })
        return context


@method_decorator(login_required, 'dispatch')
class SendInvitationView(FormView):
    # model = ConnectionDisbursementInvitation
    form_class = ConnectionDisbursementInvitationForm
    template_name = "ujjwala/connection-disbursement/send_invitation.html"

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

        sdms_info = obj.parent.get_sdms_consumer_details()
        # contact_name, contact_address
        context_dict.update({
            "name": sdms_info.get('contact_name', obj.parent.name),
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
            resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_bluebook_label_{}.prn'.format(obj.parent.id)

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


class PreInspectionConvertToView(FormView):
    # model = ConnectionDisbursementInvitation
    form_class = PreInspectionConvertForm
    template_name = "ujjwala/pre-Inspection-form/pre_inspection_conversion.html"

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
        obj.convert_inspection_type(convert_to_type=data['convert_to'])
        obj.save()
        return redirect('ujjwala:pre_inspection_form_view', type=data['convert_to'], pk=obj.pk)
