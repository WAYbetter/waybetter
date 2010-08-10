# Create your views here.
from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from ordering.forms import OrderForm, HIDDEN_FIELDS
from django.views.decorators.csrf import csrf_exempt
import order_manager
import sys
from ordering.errors import OrderError
from ordering.models import Passenger


@login_required
@csrf_exempt
def passenger_home(request):
    user = get_object_or_404(User, username = request.user.username)
    hidden_fields = HIDDEN_FIELDS
    try:
        passenger = user.passenger
    except Passenger.DoesNotExist:
        return HttpResponse ("You are not a passenger") #TODO_WB: redirect to registration

    if request.POST:
        form = OrderForm(data=request.POST, passenger=passenger)
        if form.is_valid():
            order = form.save()
            try:
                order_manager.book_order(order)
            except OrderError:
                return HttpResponse("There was an error booking your order: %s" % sys.exc_info()[1])
                
            return HttpResponse("Thanks you, your order was sent to a taxi station. You should get an SMS with your ride details shortly.")
    else:
        form = OrderForm(passenger=passenger)

    return render_to_response("passenger_home.html", locals())

