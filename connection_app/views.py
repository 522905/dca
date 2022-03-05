from django.shortcuts import render
from django.views.generic import DetailView

from connection_app.models import ConnectionApplication


def index(request):
    return render(request, 'connection_app/index.html')


# def status(request):
#     return render(request, 'connection_app/status.html')


class ApplicationDetailView(DetailView):
    model = ConnectionApplication

    def get_template_names(self):
        return 'connection_app/status.html'
