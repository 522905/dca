from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView

from domestic.models import FamilyMembers, DomesticConnectionApplication


def index(request):
    return redirect('domestic:web_form')


@method_decorator(login_required, 'dispatch')
class DomesticApplicationWebFormView(TemplateView):
    template_name = "domestic/web_form.html"

    # def get_context_data(self, **kwargs):
    #     context_data = super().get(**kwargs)
    #     form_fill_area_list = FormFillArea.objects.all()
    #     context_data = context_data.update({
    #         "form_fill_area_list": form_fill_area_list
    #     })
    #     return context_data


@method_decorator(xframe_options_exempt, 'dispatch')
@method_decorator(login_required, 'dispatch')
class DomesticApplicationIframeWebFormView(TemplateView):
    template_name = "domestic/i_web_form.html"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response


@method_decorator(login_required, 'dispatch')
class DomesticApplicationStatusView(TemplateView):
    template_name = "domestic/application_status/application_search_status.html"

    def post(self, request, *args, **kwargs):
        contact_mobile = request.POST.get('contact_mobile', '')
        uid = request.POST.get('uid', '')
        application_id = request.POST.get('application_id', '')
        application = {}

        if contact_mobile:
            application = DomesticConnectionApplication.objects.filter(contact_mobile=contact_mobile).first()
        elif uid:
            family_member = FamilyMembers.objects.filter(uid_no=uid).first()
            if family_member:
                application = family_member.parent
        elif application_id:
            application = DomesticConnectionApplication.objects.filter(id=application_id).first()

        if application:
            # reject_reason = domestic_application_reject_reason_log(application.id)
            return render(request, self.template_name, context={'obj': application, 'rejected_reason': reject_reason})
        else:
            messages.add_message(
                request, messages.ERROR, "Please Enter Contact Mobile Or Aadhaar Or Application Id To Search"
            )
        return super().get(request, *args, **kwargs)
