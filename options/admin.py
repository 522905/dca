from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin

from options.models import Banner

class BannerAdmin(SummernoteModelAdmin):
	# displaying posts with title slug and created time
	list_display = ('disabled', 'created_on', 'updated_on', 'name', 'valid_from', 'valid_upto')
	list_filter = ("disabled",)
	search_fields = ['page', 'section', 'content']
	# # prepopulating slug from title
	# prepopulated_fields = {'slug': ('title',)}
	summernote_fields = ('content',)

