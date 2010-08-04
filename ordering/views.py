# Create your views here.
from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from ordering.forms import OrderForm
from django.views.decorators.csrf import csrf_exempt

@login_required
@csrf_exempt
def passenger_home(request):
    user = get_object_or_404(User, username = request.user.username)
    if not user.passenger:
        return HttpResponse("You are not a passenger")
    else:
        passenger = user.passenger 
        
    if request.POST:
        form = OrderForm(data=request.POST, passenger=passenger)
        if form.is_valid():
            form.save()
            return HttpResponse("Thanks you, order submitted")
    else:
        form = OrderForm(passenger=passenger)

    return render_to_response("passenger_home.html", locals())
