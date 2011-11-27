# This Python file uses the following encoding: utf-8
import settings
from django import forms
from django.forms.models import ModelForm, NON_FIELD_ERRORS
from django.forms.util import flatatt, ErrorList
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import smart_unicode, force_unicode
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from common.models import Country, City
from common.util import log_event, EventType, blob_to_image_tag, Enum, phone_regexp
from common.forms import _clean_address
from ordering.models import Order, Station, Feedback, Business
from ordering.util import create_user, create_passenger

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
            result = blob_to_image_tag(value, height=80)

        return result


    def value_from_datadict(self, data, files, name):
        """
        Given a dictionary of data and this widget's name, returns the value
        of this widget. Returns None if it's not provided.
        """
        return data.get(name, None)


class AppEngineImageField(forms.FileField):
    default_error_messages = {
        'invalid_image': _(
            u"Upload a valid image. The file you uploaded was either not an image or was a corrupted image."),
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


HIDDEN_FIELDS = (
"from_country", "from_city", "from_street_address", "from_house_number", "from_geohash", "from_lon", "from_lat",
"to_country", "to_city", "to_street_address", "to_house_number", "to_geohash", "to_lon", "to_lat",)

class FeedbackForm(ModelForm):
    passenger = None
    class Meta:
        model = Feedback
        exclude = ["passenger"]

    def __init__(self, data=None, passenger=None):
        super(ModelForm, self).__init__(data)
        self.passenger = passenger


class ErrorCodes(Enum):
    COUNTRIES_DONT_MATCH = 1001
    NO_SERVICE_IN_COUNTRY = 1002
    NO_SERVICE_IN_CITY = 1003
    INVALID_ADDRESS = 1004


class CodeErrorList(ErrorList):
    def __init__(self, seq=(), code=None):
        super(ErrorList, self).__init__(seq)
        self.code = code

    def as_pure_text(self):
        if not self: return u''
        return u'\n'.join([force_unicode(e) for e in self])


class OrderForm(ModelForm):
    passenger = None

    # optional disambiguation choices
    from_address_choices = []
    to_address_choices = []
    disambiguation_choices = {}

    class Meta:
        model = Order
        fields = ["from_raw", "to_raw", "originating_station"]
        fields.extend(HIDDEN_FIELDS)

    def __init__(self, data=None, passenger=None):
        super(ModelForm, self).__init__(data)
        self.passenger = passenger
        self.disambiguation_choices = {}
        self.error_class = CodeErrorList

    def _clean_form(self):
        try:
            self.cleaned_data = self.clean()
        except ValidationError, e:
            self._errors[NON_FIELD_ERRORS] = self.error_class(e.messages, code=e.code)

    def clean(self):
        to_country = self.cleaned_data.get('to_country')
        from_country = self.cleaned_data.get('from_country')
        from_lon = self.cleaned_data.get('from_lon')
        from_lat = self.cleaned_data.get('from_lat')
        to_lon = self.cleaned_data.get('to_lon')
        to_lat = self.cleaned_data.get('to_lat')
        from_city = self.cleaned_data.get('from_city')
        to_city = self.cleaned_data.get('to_city')

        if self.passenger and self.passenger.is_banned:
            raise forms.ValidationError(_("Your account has been suspended. Please contact support@waybetter.com"))

        if to_country and from_country != to_country:
            log_event(EventType.CROSS_COUNTRY_ORDER_FAILURE, passenger=self.passenger, country=to_country)
            raise forms.ValidationError(_("To and From countries do not match"), code=ErrorCodes.COUNTRIES_DONT_MATCH)

        stations_count = Station.objects.filter(country=from_country).count()
        if not stations_count:
            log_event(EventType.NO_SERVICE_IN_COUNTRY, passenger=self.passenger, country=from_country)
            raise forms.ValidationError(_("Currently, there is no service in the country"),
                                        code=ErrorCodes.NO_SERVICE_IN_COUNTRY)

        # TODO_WB: move this check to the DB?
        close_enough_station_found = False
        stations = Station.objects.filter(country=from_country)

        user = self.passenger.user if self.passenger else None
        if user and user.is_staff:
            pass
        else:
            stations = stations.filter(show_on_list=True)

        for station in stations:
            if station.is_in_valid_distance(from_lon=from_lon, from_lat=from_lat, to_lon=to_lon, to_lat=to_lat):
                close_enough_station_found = True
                break

        if not close_enough_station_found:
            log_event(EventType.NO_SERVICE_IN_CITY, passenger=self.passenger, city=from_city, lat=from_lat,
                      lon=from_lon)
            if to_city and from_city != to_city:
                log_event(EventType.NO_SERVICE_IN_CITY, passenger=self.passenger, city=to_city, lat=to_lat, lon=to_lon)

            raise forms.ValidationError(
                _(
                    "Service is not available in %(city)s yet.\nPlease try again soon.\nTHANKS!\nWAYbetter team :)") %
                {'city': from_city.name}, code=ErrorCodes.NO_SERVICE_IN_CITY)

        return self.cleaned_data

    def save(self, commit=True):
        #TODO_WB: geocode raw address, fill city_area

        model = super(OrderForm, self).save(commit=False)
        model.passenger = self.passenger

        model.from_postal_code = '000000'
        model.to_postal_code = '000000'

        #        model.from_street_address = self.cleaned_data['from_raw']
        #        model.to_street_address = self.cleaned_data['to_raw']

        if commit:
            model.save()

        return model


class BusinessRegistrationForm(forms.ModelForm):
    class Meta():
        model = Business
        fields = ['name', 'contact_person']

    phone = forms.RegexField(regex=phone_regexp,
                             max_length=20,
                             widget=forms.TextInput(),
                             label=_("Phone"),
                             error_messages={'invalid': _("The value must contain only numbers.")})
    address = forms.CharField(label=_("Address"))

    default_station = forms.ModelChoiceField(queryset=Station.objects.filter(show_on_list=True),
                                             label=_("Default station"), empty_label=_("(No station selected)"),
                                             required=False)
    confine_orders = forms.BooleanField(label=_("Confine my orders to my default station"), required=False)


    email = forms.EmailField(label=_("Email"))
    password = forms.CharField(label=_("Enter password"), widget=forms.PasswordInput())
    password2 = forms.CharField(label=_("Re-enter password"), widget=forms.PasswordInput())

    # hidden
    from_station = forms.ModelChoiceField(queryset=Station.objects.all(), widget=forms.HiddenInput(), required=False)
    city = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    street_address = forms.CharField(widget=forms.HiddenInput(), required=False)
    house_number = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    lon = forms.FloatField(widget=forms.HiddenInput(), required=False)
    lat = forms.FloatField(widget=forms.HiddenInput(), required=False)

    class Ajax:
        rules = [
                ('password2', {'equal_to_field': 'password'}),
                ]
        messages = [
                ('password2', {'equal_to_field': _("The two password fields didn't match.")}),
                ]

    def clean_email(self):
        cleaned_email = self.cleaned_data['email']
        if User.objects.filter(username=cleaned_email).count():
            raise forms.ValidationError(_("Email already registered"))

        return cleaned_email

    def save(self, commit=True):
        model = super(BusinessRegistrationForm, self).save(commit=False)

        user = create_user(self.cleaned_data['email'], self.cleaned_data['password'],
                           email=self.cleaned_data['email'], first_name=self.cleaned_data['name'], save=False)
        passenger = create_passenger(user, Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE),
                                     self.cleaned_data['phone'], save=False)
        passenger.default_station = self.cleaned_data['default_station']

        model.address = self.cleaned_data['address']
        model.city = City.objects.get(id=self.cleaned_data['city'])
        model.street_address = self.cleaned_data['street_address']
        model.house_number = self.cleaned_data['house_number']
        model.lon = self.cleaned_data['lon']
        model.lat = self.cleaned_data['lat']

        model.confine_orders = self.cleaned_data['confine_orders']

        model.from_station = self.cleaned_data['from_station']
        
        if commit:
            user.save()
            passenger.user = user
            passenger.save()
            model.passenger = passenger
            model.save()

        return model


class StationProfileForm(forms.Form, Id2Model):
    name = forms.CharField(label=_("Station name"))
    password = forms.CharField(label=_("Change password"), widget=forms.PasswordInput(), required=False)
    password2 = forms.CharField(label=_("Re-enter password"), widget=forms.PasswordInput(), required=False)
    country_id = forms.IntegerField(widget=forms.Select(choices=Country.country_choices()), label=_("Country"))
    city_id = forms.IntegerField(widget=forms.Select(choices=[("", "-------------")]), label=_("City"))
    address = forms.CharField(label=_("Address"))
    number_of_taxis = forms.RegexField(regex=r'^\d+$',
                                       max_length=4,
                                       widget=forms.TextInput(),
                                       label=_("Number of taxis"),
                                       error_messages={'invalid': _("The value must contain only numbers.")})

    website_url = forms.CharField(label=_("Website URL"), required=False)
    #    language = form.
    email = forms.EmailField(label=_("Email"))
    #    logo = AppEngineImageField(label=_("Logo"), required=False)
    description = forms.CharField(label=_("Description"), widget=forms.Textarea, required=False)
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
    local_phone = forms.RegexField(regex=phone_regexp,
                                   max_length=20,
                                   widget=forms.TextInput(),
                                   label=_("Phone"),
                                   error_messages={'invalid': _("The value must contain only numbers.")})


class PassengerProfileForm(forms.Form):
    # TODO_WB: uncomment when we start supporting passengers from multiple countries
#    country = forms.ModelChoiceField(queryset=Country.objects.all().order_by("name"), label=_("Country"))

    default_station = forms.ModelChoiceField(queryset=Station.objects.filter(show_on_list=True),
                                             label=_("Default station"), empty_label=_("(No station selected)"),
                                             required=False)

    class Ajax:
        pass


class InternalPassengerProfileForm(PassengerProfileForm):
    first_name = forms.CharField(label=_("First name"), widget=forms.TextInput(), required=False)
    last_name = forms.CharField(label=_("Last name"), widget=forms.TextInput(), required=False)

    password = forms.CharField(label=_("Change password"), widget=forms.PasswordInput(), required=False)

    password2 = forms.CharField(label=_("Re-enter password"), widget=forms.PasswordInput(), required=False)

    class Ajax:
        rules = [
                ('password2', {'equal_to_field': 'password'}),

                ]
        messages = [
                ('password2', {'equal_to_field': _("The two password fields didn't match.")}),
                ]


class BusinessPassengerProfileForm(PassengerProfileForm):
    confine_orders = forms.BooleanField(label=_("Confine my orders to my default station"), required=False)

    contact_person = forms.CharField(label=_("contact person"))
    phone = forms.RegexField(regex=phone_regexp,
                             max_length=20,
                             widget=forms.TextInput(),
                             label=_("Phone"),
                             error_messages={'invalid': _("The value must contain only numbers.")})
    password = forms.CharField(label=_("Change password"), widget=forms.PasswordInput(), required=False)
    password2 = forms.CharField(label=_("Re-enter password"), widget=forms.PasswordInput(), required=False)

    class Ajax:
        rules = [
                ('password2', {'equal_to_field': 'password'}),

                ]
        messages = [
                ('password2', {'equal_to_field': _("The two password fields didn't match.")}),
                ]


def get_profile_form(passenger, data=None):
    """
    returns a form instance taking into account if the user was registered via a third party or internally
    """
    if passenger.business:
        return BusinessPassengerProfileForm(data=data)
    elif passenger.is_internal_passenger():
        return InternalPassengerProfileForm(data=data)
    else:
        return PassengerProfileForm(data=data)


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


class FlatRateRuleSetupForm(forms.Form):
    country = forms.ModelChoiceField(queryset=Country.objects.all())
    csv = forms.CharField(widget=forms.Textarea)


class StationAdminForm(forms.ModelForm):
    station_mobile_redirect = forms.CharField(widget=forms.Textarea(attrs={'dir':'ltr'}), required=False)

    class Meta:
        model = Station

    def __init__(self, *args, **kwargs):
        super(StationAdminForm, self).__init__(*args, **kwargs)

        if kwargs.has_key('instance'):
            instance = kwargs['instance']
            if instance.subdomain_name:
                script_src = "http://%s%s" %(settings.DEFAULT_DOMAIN, reverse('ordering.station_controller.station_mobile_redirect', kwargs={'subdomain_name': instance.subdomain_name}))
                self.initial['station_mobile_redirect'] = '<script type="text/javascript" src="%s"></script>' % script_src


    def clean_address(self):
        return _clean_address(self)