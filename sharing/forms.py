from django import forms
from django.core.exceptions import ValidationError
from common.geocode import geocode
from sharing.models import HotSpot

class TimeFrameForm(forms.ModelForm):
    def clean(self):
        by_date = bool(self.cleaned_data.get("from_date") or self.cleaned_data.get("to_date"))
        by_weekday = bool(self.cleaned_data.get("from_day") or self.cleaned_data.get("to_day"))

        if by_date and by_weekday:
            raise forms.ValidationError("Can not define time frame by both date and day.")

        elif by_date and not (self.cleaned_data.get("from_date") and self.cleaned_data.get("to_date")):
            raise ValidationError("Please enter both From and To fields")

        elif by_date and self.cleaned_data.get("from_date") > self.cleaned_data.get("to_date"):
            raise forms.ValidationError("From date should be smaller than To date.")

        elif by_weekday and not (self.cleaned_data.get("from_day") and self.cleaned_data.get("to_day")):
            raise ValidationError("Please enter both From and To fields")

        else:
            return self.cleaned_data


class HotSpotAdminForm(forms.ModelForm):
    class Meta:
        model = HotSpot

    def clean_address(self):
        if "address" in self.initial and self.cleaned_data["address"] == self.initial["address"]:
            return self.initial["address"]

        result = None
        geocode_str = u"%s %s" % (self.cleaned_data["city"], self.cleaned_data["address"])
        geocode_results = geocode(geocode_str)
        if len(geocode_results) < 1:
            raise ValidationError("Could not resolve address")
        elif len(geocode_results) > 1:
            address_options = []
            for res in geocode_results:
                address = "%s %s" % (res["street_address"], res["house_number"])
                address_options.append(address)
                if address == self.cleaned_data["address"]:
                    result = res
                    break

            if not result:
                raise ValidationError("Please choose one: %s" % ", ".join(address_options))

        else:
            result = geocode_results[0]

        self.instance.lon = result["lon"]
        self.instance.lat = result["lat"]
        self.instance.geohash = result["geohash"]

        self.cleaned_data["address"] = "%s %s" % (result["street_address"], result["house_number"])

        return self.cleaned_data["address"]


class ConstraintsForm(forms.Form):
    time_const_min = forms.IntegerField(label="Time constraint in minutes")
    time_const_frac = forms.FloatField(label="Fractional Time constraint")

    def clean(self):
        if self.cleaned_data["time_const_frac"] and self.cleaned_data["time_const_min"]:
            raise ValidationError("Please specify only one time constraint")
        return self.cleaned_data

    def clean_time_const_frac(self):
        if self.cleaned_data["time_const_frac"] < 1:
            raise ValidationError("Fractional time constraint must be bigger than 1 ")
        elif self.cleaned_data["time_const_frac"] > 2:
            raise ValidationError("Fractional time constraint must be smaller than 2")
        else:
            return self.cleaned_data["time_const_frac"]