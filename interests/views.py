# Create your views here.
from django.template.context import RequestContext
from django.shortcuts import render_to_response
from forms import MobileInterestForm
def mobile_interest(request):
    if request.method == 'POST':
        form = MobileInterestForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = MobileInterestForm()
        
    return render_to_response("mobile_interest_form.html", locals(), RequestContext(request))
