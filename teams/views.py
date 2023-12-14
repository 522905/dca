from django.shortcuts import render, redirect

# Create your views here.
from django.views.generic import ListView

from teams.models import FormFillArea


class FormFillAreaListView(ListView):
	model = FormFillArea
	template_name = 'teams/form_fill_area_list.html'

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		return FormFillArea.objects.all()

	def dispatch(self, request, *args, **kwargs):
		return redirect("https://www.arungas.com/csc-locations/index.html")
