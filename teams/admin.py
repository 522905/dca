from django.contrib import admin
from treenode.admin import TreeNodeModelAdmin
from treenode.forms import TreeNodeForm

from .models import ServiceLocations, ServiceArea, ServiceAreaMechanic


@admin.register(ServiceLocations)
class ServiceLocationsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'parent',
        'type',
        'start_working_hours',
        'end_working_hours',
        'address',
        'lat_long',
        'enabled',
    )
    list_filter = ('parent', 'enabled')


class ServiceAreaMechanicLineAdmin(admin.TabularInline):
    model = ServiceAreaMechanic
    extra = 1


@admin.register(ServiceArea)
class ServiceAreaAdmin(TreeNodeModelAdmin):
    search_fields = ('name', 'description',)
    # set the changelist display mode: 'accordion', 'breadcrumbs' or 'indentation' (default)
    # when changelist results are filtered by a querystring,
    # 'breadcrumbs' mode will be used (to preserve data display integrity)
    treenode_display_mode = TreeNodeModelAdmin.TREENODE_DISPLAY_MODE_ACCORDION
    # treenode_display_mode = TreeNodeModelAdmin.TREENODE_DISPLAY_MODE_BREADCRUMBS
    # treenode_display_mode = TreeNodeModelAdmin.TREENODE_DISPLAY_MODE_INDENTATION

    # use TreeNodeForm to automatically exclude invalid parent choices
    form = TreeNodeForm

    inlines = (ServiceAreaMechanicLineAdmin,)

# @admin.register(ServiceArea)
# class ServiceLocationsAdmin(admin.ModelAdmin):
#     list_display = (
#         'id',
#         'name',
#         'description'
#     )
#     list_filter = ('name',)
#     inlines = (ServiceAreaMechanicLineAdmin,)
