import json

import django_rq
from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, FormView, ListView
from django_currentuser.middleware import get_current_user
from django.forms import formset_factory
import ujjwala.forms
from otp.models import Otp
from ujjwala.enums import UjjwalaV2ApplicationStatus, PreInspectionStatusEnum, ConnectionDisbursementStatusEnum
from ujjwala.forms import UjjwalaDocumentsReuploadForm, PreInspectionInitialForm, \
    PreInspectionGenerateOtpForm, PreInspectionValidateOtpForm, \
    KitchenPreInspectionForm, AudioOnSafetyForm, PreviewPreInspectionForm, PreInspectionAllocatedGenerateOtpForm, \
    PreInspectionAllocatedValidateOtpForm, UjjwalaLegalDocumentsUpload, ChangeAddressForm, \
    ConnectionDisbursementLabelPrintInitialForm, InstallationMainGateUploadForm, InstallationKitchenUploadForm, \
    UjjwalaApplicationOtpInitialForm, UjjwalaApplicationGenerateOtpForm, UjjwalaApplicationValidateOtpForm, \
    ConnectionDisbursementPhotoUploadForm

from ujjwala.models import UjjwalaV2Application, PreInspection, ConnectionDisbursement


def index(request):
    return render(request, 'ujjwala/index.html')


def legal_documents(request):
    return render(request, 'ujjwala/legal_documents_upload.html')


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
class UjjwalaConnectionDisbursementListView(ListView):
    model = ConnectionDisbursement

    paginate_by = 20
    permission = 'has_view_permission'

    def get_queryset(self):
        return ConnectionDisbursement.objects.filter(
            status=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED
        )

    def get_template_names(self):
        return 'ujjwala/connection_disbursement_listview.html'

    def get(self, request, *args, **kwargs):
        application_id = request.GET.get('application_id', '')
        if application_id:
            object_list = self.get_queryset()
            object = object_list.filter(parent_id=application_id).first()
            if object:
                return redirect('ujjwala:connection_disbursement_form_view',
                    pk=object.pk
                )
        return super().get(request, *args, **kwargs)


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
        if installation_obj.status == ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED_UPLOAD_INSTALLATION:
            return InstallationKitchenUploadForm
        elif installation_obj.status == ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE:
            return InstallationMainGateUploadForm

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_template_names(self):
        installation_obj = self.get_object()
        if installation_obj.status == ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED_UPLOAD_INSTALLATION:
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
        return ConnectionDisbursement.objects.all()
        # .filter(
        #     status=PreInspectionStatusEnum.SUBMITTED
        # )

    def get_template_names(self):
        return 'ujjwala/installation_listview.html'


@method_decorator(login_required, 'dispatch')
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
        if pre_inspection.status == PreInspectionStatusEnum.ALLOCATED:
            return self.otp_verification(pre_inspection)
        elif pre_inspection.status in (
                PreInspectionStatusEnum.SUBMITTED,
                PreInspectionStatusEnum.ACCEPTED,
                PreInspectionStatusEnum.REJECTED,
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
                    mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
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
                    mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
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

                pre_inspection.pre_inspection_otp_verified(
                    by=get_current_user(),
                    description="Allocated Inspection Otp Verified, Customer Phone {}".format(otp_obj.mobile)
                )
                pre_inspection.save()

                return redirect('ujjwala:pre_inspection_form_view', pk=pre_inspection.id)

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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        pre_inspection = self.get_object()
        kwargs['pre_inspection'] = pre_inspection
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

            pre_inspection_obj = PreInspection.objects.filter(
                parent_id=app_id
            ).exclude(
                status__in=[
                    PreInspectionStatusEnum.REJECTED
                ]
            ).first()

            if pre_inspection_obj:
                return redirect('ujjwala:pre_inspection_form_view', pk=pre_inspection_obj.pk)

            app = UjjwalaV2Application.objects.filter(pk=app_id).first()
            return render(self.request, self.stage_2_template, {
                'form': PreInspectionGenerateOtpForm(
                    mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
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
                mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
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
            form = UjjwalaApplicationValidateOtpForm(data=request.POST)
            otp_obj = Otp.objects.filter(reference_number=request.POST['reference_number']).first()
            if not form.is_valid():
                return render(self.request, self.stage_3_template, {
                    'form': form,
                    'reference_number': otp_obj.reference_number,
                    'mobile': otp_obj.mobile
                })
            app_id = form.data.get('application_id')
            obj = PreInspection.objects.create(
                parent_id=app_id,
                status=PreInspectionStatusEnum.ALLOCATED,
                mechanic=get_current_user()
            )
            obj.pre_inspection_otp_verified(
                by=get_current_user(),
                description="Instant Inspection Created, Customer Phone {}".format(otp_obj.mobile)
            )
            obj.save()

            return redirect('ujjwala:pre_inspection_form_view', pk=obj.pk)


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

        if connection_disbursement.status in (
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REJECTED,
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
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
class ConnectionDisbursementLabelPrintView(View):
    model = ConnectionDisbursement
    stage_1_template = 'ujjwala/generate_otp_form.html'
    stage_2_template = 'ujjwala/pre_inspection_generate_otp_form.html'
    stage_3_template = 'ujjwala/pre_inspection_validate_otp_form.html'

    def get(self, request, *args, **kwargs):
        return render(self.request, self.stage_1_template, {
            'form': ConnectionDisbursementLabelPrintInitialForm()
        })

    def post(self, request, *args, **kwargs):
        if self.request.POST.get('form_type') == 'initial_form':
            form = ConnectionDisbursementLabelPrintInitialForm(data=request.POST)

            if not form.is_valid():
                return render(self.request, self.stage_1_template, {
                    'form': form
                })
            app_id = form.data.get('application_id')

            pre_inspection_obj = PreInspection.objects.filter(
                parent_id=app_id
            ).exclude(
                status__in=[
                    PreInspectionStatusEnum.REJECTED
                ]
            ).first()

            if pre_inspection_obj:
                return redirect('ujjwala:pre_inspection_form_view', pk=pre_inspection_obj.pk)

            app = UjjwalaV2Application.objects.filter(pk=app_id).first()
            return render(self.request, self.stage_2_template, {
                'form': PreInspectionGenerateOtpForm(
                    mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
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
                mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
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
            form = PreInspectionValidateOtpForm(data=request.POST)
            otp_obj = Otp.objects.filter(reference_number=request.POST['reference_number']).first()
            if not form.is_valid():
                return render(self.request, self.stage_3_template, {
                    'form': form,
                    'reference_number': otp_obj.reference_number,
                    'mobile': otp_obj.mobile
                })
            app_id = form.data.get('application_id')
            obj = PreInspection.objects.create(
                parent_id=app_id,
                status=PreInspectionStatusEnum.ALLOCATED,
                mechanic=get_current_user()
            )
            obj.pre_inspection_otp_verified(
                by=get_current_user(),
                description="Instant Inspection Created, Customer Phone {}".format(otp_obj.mobile)
            )
            obj.save()
            return redirect('ujjwala:pre_inspection_form_view', pk=obj.pk)


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementMaterialDeliveryView(View):
    model = ConnectionDisbursement
    stage_1_template = 'ujjwala/application_initial_form.html'
    stage_2_template = 'ujjwala/generate_otp_form.html'
    stage_3_template = 'ujjwala/validate_otp_form.html'

    def get(self, request, *args, **kwargs):
        return render(self.request, self.stage_1_template, {
            'form': UjjwalaApplicationOtpInitialForm()
        })

    def post(self, request, *args, **kwargs):
        if self.request.POST.get('form_type') == 'initial_form':
            form = UjjwalaApplicationOtpInitialForm(data=request.POST)

            if not form.is_valid():
                return render(self.request, self.stage_1_template, {
                    'form': form
                })
            app_id = form.data.get('application_id')

            connection_disbursement_obj = ConnectionDisbursement.objects.filter(
                parent_id=app_id
            ).exclude(
                status__in=[
                    ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED
                ]
            ).first()

            if connection_disbursement_obj:
                return redirect('ujjwala:pre_inspection_form_view', pk=connection_disbursement_obj.pk)

            app = UjjwalaV2Application.objects.filter(pk=app_id).first()
            return render(self.request, self.stage_2_template, {
                'form': UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
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
                mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
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
            form = PreInspectionValidateOtpForm(data=request.POST)
            otp_obj = Otp.objects.filter(reference_number=request.POST['reference_number']).first()
            if not form.is_valid():
                return render(self.request, self.stage_3_template, {
                    'form': form,
                    'reference_number': otp_obj.reference_number,
                    'mobile': otp_obj.mobile
                })
            app_id = form.data.get('application_id')
            obj = PreInspection.objects.create(
                parent_id=app_id,
                status=PreInspectionStatusEnum.ALLOCATED,
                mechanic=get_current_user()
            )
            obj.pre_inspection_otp_verified(
                by=get_current_user(),
                description="Instant Inspection Created, Customer Phone {}".format(otp_obj.mobile)
            )
            obj.save()
            return redirect('ujjwala:connection_disbursement_form_view', pk=obj.pk)


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementView(FormView):
    model = ConnectionDisbursement
    connection_disbursement_step0_template = ''
    connection_disbursement_step1_template = 'ujjwala/disbursement_photo_upload.html'
    success_url = '.'

    stage_1_generate_otp = 'ujjwala/generate_otp_form.html'
    stage_2_validate_otp = 'ujjwala/validate_otp_form.html'

    def dispatch(self, request, *args, **kwargs):
        connection_disbursement = ConnectionDisbursement.objects.get(pk=kwargs.get('pk'))
        if connection_disbursement.status == ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED:
            return self.otp_verification(connection_disbursement)
        elif connection_disbursement.status in (
                ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
                ConnectionDisbursementStatusEnum.DISBURSEMENT_PHOTO_UPLOAD
                # ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE,
                # ConnectionDisbursementStatusEnum.OTP_VERIFIED
        ):
            # return render(self.request, '', context={
            #     'connection_disbursement': connection_disbursement
            # })
            return HttpResponse(content='Status: {}'.format(connection_disbursement.status))
        return super().dispatch(request, *args, **kwargs)

    def otp_verification(self, connection_disbursement):
        context = {'connection_disbursement': connection_disbursement, 'application': connection_disbursement.parent}

        if self.request.method.lower() == 'get':
            app = connection_disbursement.parent
            context.update({
                'form': UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
                    initial={
                        'connection_disbursement_id': connection_disbursement.id,
                        'application_id': connection_disbursement.parent_id,
                        'whatsapp_template_name': 'connection_disbursement_dac',
                        'otp_generated_for': 'ConnectionDisbursement',
                    }
                )
            })
            return render(self.request, self.stage_1_generate_otp, context)
        elif self.request.method.lower() == 'post':
            if self.request.POST.get('form_type') == 'generate_otp_form':
                app = UjjwalaV2Application.objects.get(pk=connection_disbursement.parent_id)
                form = UjjwalaApplicationGenerateOtpForm(
                    mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
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

                connection_disbursement.transition_connection_disbursement_otp_verified(
                    by=get_current_user(),
                    description="Allocated Connection Disbursement Otp Verified, Customer Phone {}".format(otp_obj.mobile)
                )
                connection_disbursement.save()

                connection_disbursement.transition_sv_label_printed(
                    by=get_current_user(),
                    description="SV Label Print Skipped"
                )
                connection_disbursement.save()

                return redirect('ujjwala:connection_disbursement_form_view', pk=connection_disbursement.id)

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
        application = self.get_object()

        if application.status == ConnectionDisbursementStatusEnum.SV_LABEL_PRINT:
            return ConnectionDisbursementPhotoUploadForm

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_template_names(self):
        connection_disbursement_obj = self.get_object()
        if connection_disbursement_obj.status == ConnectionDisbursementStatusEnum.SV_LABEL_PRINT:
            return self.connection_disbursement_step1_template

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
