# This Python file uses the following encoding: utf-8

from django import forms
from django.forms.models import ModelForm
from django.forms.util import flatatt
from django.utils.translation import gettext as _
from django.utils.encoding import smart_unicode

from common.models import Country, City
from ordering.models import Order, Station
from django.utils.safestring import mark_safe
from google.appengine.api.images import BadImageError, NotImageError

INITIAL_DATA = 'INITIAL_DATA'

class Id2Model():
    def id_field_to_model(self, field_name, model):
        if hasattr(self, "cleaned_data"):
            if (field_name in self.cleaned_data) and (self.cleaned_data[field_name]):
                try:
                    instance = model.objects.get(id=self.cleaned_data[field_name])
                    self.cleaned_data[field_name] = instance
                except:
                    self.cleaned_data[field_name] = None

class AppEngineImageWidget(forms.FileInput):
    def render(self, name, value, attrs=None):
        result = super(AppEngineImageWidget, self).render(name, None, attrs=attrs)
        if value:
            import base64
            from google.appengine.api import images
            try:
                img = images.Image(value)
                img.resize(height=80)
                thumbnail = img.execute_transforms(output_encoding=images.PNG)
                result = u"""<img src='data:image/png;base64,%s' /><br>""" % base64.encodestring(thumbnail) + result
            except BadImageError:
                pass
            except NotImageError:
                pass

        return result


    def value_from_datadict(self, data, files, name):
        """
        Given a dictionary of data and this widget's name, returns the value
        of this widget. Returns None if it's not provided.
        """
        return data.get(name, None)
class AppEngineImageField(forms.FileField):
    default_error_messages = {
        'invalid_image': _(u"Upload a valid image. The file you uploaded was either not an image or was a corrupted image."),
    }
    widget = AppEngineImageWidget
    
    def clean(self, data, initial=None):

        raw_file = super(AppEngineImageField, self).clean(data, initial)
        if raw_file is None:
            return None
        elif not data and initial:
            return initial

        if (len(raw_file) > 0) and (not self._image_bytes_are_valid(raw_file)):
            raise forms.ValidationError(self.error_messages['invalid_image'])

        return raw_file

    def to_python(self, data):
        from django.core import validators

        if data in validators.EMPTY_VALUES or data == 'None': # for some reason 'None' is being set for empty images
            return None

        return data

    def _image_bytes_are_valid(self, image_bytes):
        from google.appengine.api import images
        try:
            # Unfortunately the only way to validate image bytes on AppEngine is to
            # perform a transform. Lame.
            images.im_feeling_lucky(image_bytes)
        except images.BadImageError:
            return False
        return True


HIDDEN_FIELDS = ("from_country", "from_city", "from_street_address", "from_geohash", "from_lon", "from_lat",
                 "to_country", "to_city", "to_street_address", "to_geohash", "to_lon", "to_lat",)

class OrderForm(ModelForm):
    passenger = None

    # optional disambiguation choices
    from_address_choices = []
    to_address_choices = []
    disambiguation_choices = {}

    class Meta:
        model = Order
        fields = ["from_raw", "to_raw"]
        fields.extend(HIDDEN_FIELDS)

    def __init__(self, data=None, passenger=None):
        super(ModelForm, self).__init__(data)
        self.passenger = passenger
        self.disambiguation_choices = {}


    def clean(self):
        if self.cleaned_data['from_country'] != self.cleaned_data['to_country']:
            raise forms.ValidationError(_("To and From countries do not match"))

        return self.cleaned_data

    def save(self, commit=True):
        #TODO_WB: geocode raw address, fill city_area
        
        model = super(OrderForm, self).save(commit=False)
        model.passenger = self.passenger

        model.form_postal_code = '000000'
        model.to_postal_code = '000000'

#        model.from_street_address = self.cleaned_data['from_raw']
#        model.to_street_address = self.cleaned_data['to_raw']

        if commit:
            model.save()

        return model

class StationProfileForm(forms.Form, Id2Model):

    name = forms.CharField(label=_("Station name"))
    password = forms.CharField(label=_("Change password"), widget=forms.PasswordInput(), required=False)
    password2 = forms.CharField(label=_("Re-enter password"), widget=forms.PasswordInput(), required=False)
    country_id = forms.IntegerField(widget=forms.Select(choices=Country.country_choices()), label=_("Country"))
    city_id = forms.IntegerField(widget=forms.Select(choices=[("", "-------------")]), label=_("City"))
    address = forms.CharField(label=_("Address"))
    number_of_taxis = forms.RegexField( regex=r'^\d+$',
                                    max_length=4,
                                    widget=forms.TextInput(),
                                    label=_("Number of taxis"),
                                    error_messages={'invalid': _("The value must contain only numbers.")})

    website_url = forms.CharField(label=_("Website URL"), required=False)
#    language = form.
    email = forms.EmailField(label=_("Email"))
    logo = AppEngineImageField(label=_("Logo"), required=False)
    description  = forms.CharField(label=_("Description"), widget=forms.Textarea, required=False)
    lon = forms.FloatField(widget=forms.HiddenInput(), required=False)
    lat = forms.FloatField(widget=forms.HiddenInput(), required=False)

    class Ajax:
        rules = [
            ('password2', {'equal_to_field': 'password'}),
        ]
        messages = [
            ('password2', {'equal_to_field': _("The two password fields didn't match.")}),
        ]

    def clean_address(self):
        if not INITIAL_DATA in self.data:
            if not (self.data['lon'] and self.data['lat']):
                raise forms.ValidationError(_("Invalid address"))
 
        return self.cleaned_data['address']

         
    def clean(self):
        """
        """
        self.id_field_to_model('country_id', Country)
        self.id_field_to_model('city_id', City)

        self.cleaned_data['city'] = self.cleaned_data['city_id']
        self.cleaned_data['country'] = self.cleaned_data['country_id']
 
        return self.cleaned_data

class PhoneForm(ModelForm):
    local_phone = forms.RegexField( regex=r'^\d+$',
                              max_length=20,
                              widget=forms.TextInput(),
                              label=_("Phone"),
                              error_messages={'invalid': _("The value must contain only numbers.")} )
        

class PassengerProfileForm(forms.Form, Id2Model):
    email = forms.EmailField(label=_("Email"))

    password =  forms.CharField(label=_("Change password"), widget=forms.PasswordInput(), required=False)

    password2 = forms.CharField(label=_("Re-enter password"), widget=forms.PasswordInput(), required=False)

    country =   forms.ModelChoiceField(queryset=Country.objects.all().order_by("name"), label=_("Country"))

    default_station = forms.ModelChoiceField(queryset=Station.objects.all(), label=_("Default station"), empty_label=_("(No station selected)"), required=False)

    phone =     forms.RegexField( regex=r'^\d+$',
                                  max_length=20,
                                  widget=forms.TextInput(),
                                  label=_("Local mobile phone #"),
                                  error_messages={'invalid': _("The value must contain only numbers.")} )

    phone_verification_code = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    
    class Ajax:
        rules = [
            ('password2', {'equal_to_field': 'password'}),

        ]
        messages = [
            ('password2', {'equal_to_field': _("The two password fields didn't match.")}),
        ]

class CityChoiceWidget(forms.Select):
    def render(self, name, value, attrs=None, choices=()):
        self.choices = [(u"", u"---------")]
        if value is None:
            # if no municipality has been previously selected,
            # render either an empty list or, if a county has
            # been selected, render its municipalities
            value = ''
            model_obj = self.form_instance.instance
            if model_obj and model_obj.county:
                for m in model_obj.county.municipality_set.all():
                    self.choices.append((m.id, smart_unicode(m)))
        else:
            # if a municipality X has been selected,
            # render only these municipalities, that belong
            # to X's county
            obj = Municipality.objects.get(id=value)
            for m in Municipality.objects.filter(county=obj.county):
                self.choices.append((m.id, smart_unicode(m)))

        # copy-paste from widgets.Select.render
        final_attrs = self.build_attrs(attrs, name=name)
        output = [u'<select%s>' % flatatt(final_attrs)]
        options = self.render_options(choices, [value])
        if options:
            output.append(options)
        output.append('</select>')
        return mark_safe(u'\n'.join(output))

