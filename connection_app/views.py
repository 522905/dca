from django.shortcuts import render
from django.views.generic import DetailView

from connection_app.models import ConnectionApplication


def index(request):
    return render(request, 'connection_app/fblike.html')


def application_create(request):
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
