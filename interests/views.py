# Create your views here.
from django.template.context import RequestContext
from django.shortcuts import render_to_response
from forms import MobileInterestForm
from interests.forms import StationInterestForm

def mobile_interest(request):
    if request.method == 'POST':
        form = MobileInterestForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = MobileInterestForm()
        
    return render_to_response("mobile_interest_form.html", locals(), RequestContext(request))

def station_interest(request):
    if request.method == 'POST':
        form = StationInterestForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = StationInterestForm()

    return render_to_response("station_interest_form.html", locals(), RequestContext(request))
