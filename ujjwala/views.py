import json

import django_rq
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, FormView, ListView

from ujjwala.enums import UjjwalaV2ApplicationStatus
from ujjwala.forms import UjjwalaDocumentsReuploadForm, PreInspectionWizardForm
from ujjwala.models import UjjwalaV2Application


def index(request):
    return render(request, 'ujjwala/index.html')


class ApplicationStatusView(DetailView):
    model = UjjwalaV2Application

    def get_template_names(self):
        return 'ujjwala/status.html'


@method_decorator(login_required, 'dispatch')
class UjjwalaPreInspectionListView(ListView):
    model = UjjwalaV2Application
    queryset = UjjwalaV2Application.objects.filter(
        status=UjjwalaV2ApplicationStatus.NIC_CLEARED
    )
    paginate_by = 20
    permission = 'has_view_permission'

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
#     def get_initial(self):
#         """
#         Returns the initial data to use for forms on this view.
#         """
#         initial = super().get_initial()
#
#         initial['application_id'] = self.kwargs.get('pk')
#
#         return initial

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
