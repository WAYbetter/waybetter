# Create your views here.
from django.template.context import RequestContext
from django.shortcuts import render_to_response
from djangotoolbox.http import JSONResponse
from forms import MobileInterestForm, StationInterestForm, BusinessInterestForm
from interests.forms import PilotInterestForm, HotspotInterestForm, M2MInterestForm

def interest_view(request, interest_form, interest_form_template):
    if request.method == 'POST':
        response = ''
        form = interest_form(request.POST)
        if form.is_valid():
            interest = form.save()
            if hasattr(interest, "notify"):
                interest.notify()
        else:
            errors = [{e: form.errors.get(e)} for e in form.errors.keys()]
            response = {"errors": errors}

        return JSONResponse(response)

    else:
        form = interest_form()
        return render_to_response(interest_form_template, locals(), RequestContext(request))

def mobile_interest(request):
    return interest_view(request, MobileInterestForm, "mobile_interest_form.html")

def station_interest(request):
    return interest_view(request, StationInterestForm, "station_interest_form.html")

def business_interest(request):
    return interest_view(request, BusinessInterestForm, "business_interest_form.html")

def pilot_interest(request):
    return interest_view(request, PilotInterestForm, "pilot_interest_form.html")

def m2m_interest(request):
    return interest_view(request, M2MInterestForm, "m2m_interest_form.html")

def hotspot_interest(request):
    return interest_view(request, HotspotInterestForm, "hotspot_interest_form.html")

def pilot_interest_email(request):
    return render_to_response("pilot_interest_email.html")