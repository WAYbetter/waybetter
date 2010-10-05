# Copyright 2009 Tim Savage <tim.savage@jooceylabs.com>
# See LICENSE for licence information

from django.forms import Form
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext as _

from ajax_forms.utils import LazyEncoder


def validate(request, form_class, field_name):
    if not issubclass(form_class, Form):
        raise TypeError(_("Expected Django Form"))

    # Security check
    ajax_directives = getattr(form_class, 'Ajax', None)
    callback_fields = getattr(ajax_directives, 'callback_fields', [])
    if field_name not in callback_fields:
        return HttpResponse('Invalid field', status=500, mimetype="text/plain")

    # Create field and retrieve data
    form = form_class()
    field = form.fields.get(field_name)

    value = request.POST.get(field)


    #~ try:
        #~ if isinstance(field, FileField):
            #~ initial = self.initial.get(name, field.initial)
            #~ value = field.clean(value, initial)
        #~ else:
            #~ value = field.clean(value)
        #~ self.cleaned_data[name] = value
        #~ if hasattr(self, 'clean_%s' % name):
            #~ value = getattr(self, 'clean_%s' % name)()
            #~ self.cleaned_data[name] = value
    #~ except ValidationError, e:
        #~ self._errors[name] = e.messages
        #~ if name in self.cleaned_data:
            #~ del self.cleaned_data[name]
#~
#~
    #~ form_instance = form()

    return HttpResponse('not implimented: ', status=500, mimetype="text/plain")

#validate = require_POST(validate)


def validate_secure(request, *args, **kwargs):
    if not request.user.is_authenticated():
        return HttpResponse('authentication required', status=401,
            mimetype="text/plain")
    return validate(request, *args, **kwargs)
