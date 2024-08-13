from django.contrib import admin
from leaflet.admin import LeafletGeoAdminMixin
from treenode.admin import TreeNodeModelAdmin
from treenode.forms import TreeNodeForm

from .models import ServiceLocations, ServiceArea, ServiceAreaUserProfile, FormFillArea, UserProfile, \
    UserProfileDocuments, SDMSUser, SDMSServiceArea


@admin.register(ServiceLocations)
class ServiceLocationsAdmin(LeafletGeoAdminMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'parent',
        'type',
        'start_working_hours',
        'end_working_hours',
        'address',
        'enabled',
    )
    list_filter = ('parent', 'enabled')


@admin.register(FormFillArea)
class FormFillAreaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'service_location',
    )
    list_filter = ('name', 'service_location')


class ServiceAreaUserProfileLineAdmin(admin.TabularInline):
    model = ServiceAreaUserProfile
    extra = 1


class SDMSServiceAreaInlineAdmin(admin.TabularInline):
    model = SDMSServiceArea
    extra = 1


@admin.register(SDMSServiceArea)
class SDMSServiceAreaAdmin(admin.ModelAdmin):
    list_display = ['distributor', 'area_code', 'area_name']
    list_filter = ['distributor']


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

    inlines = (ServiceAreaUserProfileLineAdmin,)

# @admin.register(ServiceArea)
# class ServiceLocationsAdmin(admin.ModelAdmin):
#     list_display = (
#         'id',
#         'name',
#         'description'
#     )
#     list_filter = ('name',)
#     inlines = (ServiceAreaMechanicLineAdmin,)


class UserProfileDocumentsInline(admin.TabularInline):
    extra = 0
    model = UserProfileDocuments
    template = 'teams/admin/document-inline.html'


class UserProfileSDMSUserInline(admin.TabularInline):
    extra = 0
    model = SDMSUser
    # template = 'teams/admin/document-inline.html'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):

    def sdms_info(self, obj: UserProfile):
        delivery_boy = ", ".join(
            [
                "{} - {}".format(o.delivery_boy_login, o.delivery_boy_full_name) \
                for o in obj.sdmsuser_set.filter()
            ]
        )
        return delivery_boy

    list_display = ('id', 'user', 'type', 'sdms_info',)
    list_filter = ('type',)
    filter_horizontal = ['sdms_service_areas', ]
    inlines = [
        UserProfileDocumentsInline, UserProfileSDMSUserInline,
    ]
