from django import forms
from django.contrib import admin
from flatpages2.models import FlatPage
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from tinymce.widgets import TinyMCE


class FlatpageForm(forms.ModelForm):
    url = forms.RegexField(label=_("URL"), max_length=100, regex=r'^[-\w/]+$',
        help_text = _("Example: '/about/contact/'. Make sure to have leading"
                      " and trailing slashes."),
        error_message = _("This value must contain only letters, numbers,"
                          " underscores, dashes or slashes."))

    class Meta:
        model = FlatPage


class FlatPageAdmin(admin.ModelAdmin):
    form = FlatpageForm
    fieldsets = (
        (None, {'fields': ('url', 'title', 'content')}),
        (_('Advanced options'), {'classes': ('collapse',), 'fields': ('enable_comments', 'registration_required', 'template_name')}),
    )
    list_display = ('url', 'title')
    list_filter = ('enable_comments', 'registration_required')
    search_fields = ('url', 'title')
    save_on_top = True


class TinyMCEFlatPageAdmin(FlatPageAdmin):
    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'content':
            return db_field.formfield(widget=TinyMCE(
                attrs={'cols': 80, 'rows': 30},
                mce_attrs={'external_link_list_url': reverse('tinymce.views.flatpages_link_list')},
            ))
        return super(TinyMCEFlatPageAdmin, self).formfield_for_dbfield(db_field, **kwargs)

admin.site.register(FlatPage, TinyMCEFlatPageAdmin)