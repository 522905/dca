import json

import django_rq
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, FormView, ListView
from django_currentuser.middleware import get_current_user

from otp.models import Otp
from ujjwala.enums import UjjwalaV2ApplicationStatus, PreInspectionStatusEnum
from ujjwala.forms import UjjwalaDocumentsReuploadForm, PreInspectionInitialForm, \
    PreInspectionGenerateOtpForm, PreInspectionValidateOtpForm, \
    KitchenPreInspectionForm, AudioOnSafetyForm, PreviewPreInspectionForm, PreInspectionAllocatedGenerateOtpForm, \
    PreInspectionAllocatedValidateOtpForm
from ujjwala.models import UjjwalaV2Application, PreInspection


def index(request):
    return render(request, 'ujjwala/index.html')


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
class UjjwalaApplicationReuploadView(DetailView):
    model = UjjwalaV2Application

    def get_template_names(self):
        return 'ujjwala/ujjwala_documents_reupload.html'


# class PreInspectionWizardFormView(FormView):
#     form_class = PreInspectionWizardForm
#
#

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
class PreInspectionView(FormView):
    model = PreInspection
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
        if application.status == PreInspectionStatusEnum.KITCHEN_PHOTO:
            return KitchenPreInspectionForm
        elif application.status == PreInspectionStatusEnum.SAFETY_AUDIO:
            return AudioOnSafetyForm
        elif application.status == PreInspectionStatusEnum.PREVIEW_INSPECTION:
            return PreviewPreInspectionForm

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(self.get_success_url())

    # def get_form(self, form_class=None):
    #     application = self.get_object()
    #     if application.status == PreInspectionStatusEnum.KITCHEN_PHOTO:
    #         return KitchenPreInspectionForm(data=self.request.POST)
    #     elif application.status == PreInspectionStatusEnum.SAFETY_AUDIO:
    #         return AudioOnSafetyForm(data=self.request.POST)
    #     elif application.status == PreInspectionStatusEnum.PREVIEW_INSPECTION:
    #         return PreviewPreInspectionForm(data=self.request.POST)

    def get_template_names(self):
        preinspection_obj = self.get_object()
        if preinspection_obj.status == PreInspectionStatusEnum.KITCHEN_PHOTO:
            return self.pre_inspection_step1_template
        elif preinspection_obj.status == PreInspectionStatusEnum.SAFETY_AUDIO:
            return self.pre_inspection_step2_template
        elif preinspection_obj.status == PreInspectionStatusEnum.PREVIEW_INSPECTION:
            return self.pre_inspection_step3_template

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        pre_inspection = self.get_object()
        kwargs['pre_inspection'] = pre_inspection
        return kwargs


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
                status__in=[PreInspectionStatusEnum.ACCEPTED, PreInspectionStatusEnum.REJECTED]
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


# class PreInspectionAllocatedOtpView(View):


    # def get(self, request, *args, **kwargs):
    #     preinspection_obj = PreInspection.objects.filter(pk=kwargs.get('pk')).first()
    #     app = preinspection_obj.parent
    #     return render(self.request, self.stage_1_template, {
    #         'form': PreInspectionAllocatedGenerateOtpForm(
    #             mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
    #             data=request.POST,
    #         )
    #     })
    #
    # def post(self, request, *args, **kwargs):
    #     if self.request.POST.get('form_type') == 'generate_otp_form':
    #         app_id = self.request.POST.get('application_id')
    #         app = UjjwalaV2Application.objects.filter(pk=app_id).first()
    #         form = PreInspectionAllocatedGenerateOtpForm(
    #             mobile_nos=list({app.contact_mobile, app.uid_linked_mobile}),
    #             data=request.POST
    #         )
    #         if not form.is_valid():
    #             return render(self.request, self.stage_2_template, {
    #                 'form': form,
    #                 'application': app
    #             })
    #         otp_obj = form.send_otp()
    #         app_id = form.data.get('application_id')
    #         return render(self.request, self.stage_3_template, {
    #             'form': PreInspectionValidateOtpForm(
    #                 initial={
    #                     'application_id': app_id,
    #                     'reference_number': otp_obj.reference_number,
    #                     'mobile': otp_obj.mobile
    #                 }
    #             )
    #         })
    #     elif self.request.POST.get('form_type') == 'validate_otp_form':
    #         form = PreInspectionAllocatedValidateOtpForm(data=request.POST)
    #         if not form.is_valid():
    #             otp_obj = Otp.objects.filter(reference_number=request.POST['reference_number']).first()
    #             return render(self.request, self.stage_3_template, {
    #                 'form': form,
    #                 'reference_number': otp_obj.reference_number,
    #                 'mobile': otp_obj.mobile
    #             })
    #         app_id = form.data.get('application_id')
    #         obj = PreInspection.objects.create(
    #             parent_id=app_id,
    #             status=PreInspectionStatusEnum.KITCHEN_PHOTO,
    #             mechanic=get_current_user()
    #         )
    #         return redirect('ujjwala:pre_inspection', pk=obj.pk)

# @method_decorator(login_required, 'dispatch')
# class PreInspectionStep1(FormView):
#     model = PreInspection
#
#     def get_template_names(self):
#         return 'ujjwala/customer-kitchen.html'
#
#
# @method_decorator(login_required, 'dispatch')
# class PreInspectionStep2(FormView):
#     model = PreInspection
#
#     def get_template_names(self):
#         return 'ujjwala/witness.html'
#
#
# @method_decorator(login_required, 'dispatch')
# class PreInspectionStep3(FormView):
#     model = PreInspection
#
#     def get_template_names(self):
#         return 'ujjwala/ujjwala_documents_reupload.html'
#
#
# @method_decorator(login_required, 'dispatch')
# class PreInspectionStep4(FormView):
#     model = PreInspection
#
#     def get_template_names(self):
#         return 'ujjwala/preview_pre_inspection.html'
