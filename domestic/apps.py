from django.apps import AppConfig
from material.frontend.apps import ModuleMixin


class DomesticConfig(ModuleMixin, AppConfig):
    name = 'domestic'
    default_auto_field = 'django.db.models.BigAutoField'
    icon = '<i class="material-icons">flight_takeoff</i>'
