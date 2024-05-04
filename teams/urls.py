from django.urls import path, include

from teams.views import FormFillAreaListView

urlpatterns = [
    path('form_fill_areas/', FormFillAreaListView.as_view(), name="form_fill_area_list_view"),
]