from djangotoolbox.fields import ListField
from django.utils import simplejson
from django.utils.safestring import mark_safe
from django.conf import settings
from django.utils.encoding import smart_unicode
from django.forms import models
from django import forms
from django.db import models as db_models

class ColorPickerWidget(forms.TextInput):
    # required jquery and jquery colorPicker present in the page
    class Media:
        pass
#        css = {
#            'all': (
#                settings.MEDIA_URL + 'cssjs/colorPicker.css',
#                )
#        }
#        js = (
#            'http://ajax.googleapis.com/ajax/libs/jquery/1.2.6/jquery.min.js',
#            settings.MEDIA_URL + 'cssjs/jquery.colorPicker.js',
#            )

    def __init__(self, language=None, attrs=None):
        self.language = language or settings.LANGUAGE_CODE[:2]
        super(ColorPickerWidget, self).__init__(attrs=attrs)

    def render(self, name, value, attrs=None):
        rendered = super(ColorPickerWidget, self).render(name, value, attrs)
        return rendered + mark_safe(u'''<script type="text/javascript">
            $('#id_%s').colorPicker();
            </script>''' % name)

class ListFieldWithUI(ListField):
    def formfield(self, **kwargs):
        return FormListField(**kwargs)

class ListFieldWidget(forms.HiddenInput):
    is_hidden = False

    def _format_value(self, value):
        if isinstance(value, list):
            return "|".join([str(v) for v in value])
        return value

    def render(self, name, value, attrs=None):
        res = super(ListFieldWidget, self).render(name, value, attrs)
        button = """<button type='button' class='edit-polygon' id='edit-%s'>Edit</button>""" % attrs['id']
        return mark_safe(res + button)

class FormListField(forms.CharField):
    widget = ListFieldWidget
    def clean(self, value):
        if value:
            return value.split("|")
        return []

class ColorField(db_models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 10
        super(ColorField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        kwargs['widget'] = ColorPickerWidget
        return super(ColorField, self).formfield(**kwargs)


class CityAreaWidget(forms.Select):
    def __init__(self, language=None, attrs=None):
        self.language = language or settings.LANGUAGE_CODE[:2]
        super(CityAreaWidget, self).__init__(attrs=attrs)

    def render(self, name, value, attrs=None, choices=()):
        rendered = super(CityAreaWidget, self).render(name, value, attrs, choices)
        return rendered + mark_safe(u'''<script type="text/javascript">
            setTimeout(function() {
                $(document).data("colors", %s);
                initColors('#id_%s');
            }, 100);
            </script>''' % (simplejson.dumps(self.choices.field.colors), name))

class CityAreaFormField(models.ModelChoiceField):
    colors = {}

    def __init__(self, queryset, **kwargs):
        kwargs['widget'] = CityAreaWidget
        super(CityAreaFormField, self).__init__(queryset, **kwargs)

    def label_from_instance(self, obj):
        self.colors[obj.id] = obj.color

        return smart_unicode(obj)
