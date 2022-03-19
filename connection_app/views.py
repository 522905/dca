from django.shortcuts import render, redirect
from django.views.generic import DetailView

from connection_app.models import ConnectionApplication


def installation_upload_process_gleam_entry_gate(request):
    application_id = request.GET.get("application_id")
    response = render(request, 'connection_app/fblike.html')
    response.set_cookie('application_id_cookie', application_id)
    return response


def installation_upload_process_gleam_entry_gate_completed(request):
    application_id = request.COOKIES.get('application_id_cookie')
    return redirect('installation_start', pk=application_id)


def index(request):
    return render(request, 'connection_app/index.html')


class ApplicationStatusView(DetailView):
    model = ConnectionApplication

    def get_template_names(self):
        return 'connection_app/status.html'


class ApplicationReuploadView(DetailView):
    model = ConnectionApplication

    def get_template_names(self):
        return 'connection_app/pendingdata.html'


class ApplicationInstallationView(DetailView):
    model = ConnectionApplication

    def get_template_names(self):
        return 'connection_app/kitchenphoto.html'
