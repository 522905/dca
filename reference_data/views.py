from django.views.generic import TemplateView

from reference_data.models import HTMLTemplate
from utils.global_functions import unsign_data_base64


class HTMLTemplateView(TemplateView):

	def dispatch(self, request, *args, **kwargs):
		return super().dispatch(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		data = unsign_data_base64(kwargs.get('data'))
		context.update(
			data.get('variables')
		)
		return context

	def get_template_names(self):
		data = unsign_data_base64(self.kwargs.get('data'))
		html_template = HTMLTemplate.objects.get(template_name=data.get('template'))
		return "reference_data/html_template/{}.html".format(html_template.html_file_name)

