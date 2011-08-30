# Create your views here.
import logging
from billing import billing_backend
from django.views.decorators.csrf import csrf_exempt
from billing.models import BillingForm, InvalidOperationError
from common.decorators import require_parameters, internal_task_on_queue, catch_view_exceptions
from django.http import HttpResponse
from billing.billing_manager import get_transaction_id
from django.shortcuts import render_to_response
from django.template.context import RequestContext

def get_token(request):
    txId = get_transaction_id()
    url = "https://cgmpiuat.creditguard.co.il/CGMPI_Server/PerformTransaction?txId=%s" % txId
    form = BillingForm()
    
    #    return HttpResponseRedirect("https://cgmpiuat.creditguard.co.il/CGMPI_Server/PerformTransaction?txId=%s" % txId)
    return render_to_response("token_form.html", locals(), RequestContext(request))

def bill_passenger(request):
    form = BillingForm(data=request.POST)
    if form.is_valid():
        billing_tx = form.save()
        billing_tx.commit()

    return HttpResponse("OK")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
@require_parameters(method="POST", required_params=("token", "amount", "card_expiration", "billing_transaction_id", "action"))
def billing_task(request, token, amount, card_expiration, billing_transaction_id, action):
    if action == "commit":
        return billing_backend.do_J5(token, amount, card_expiration, billing_transaction_id)
    elif action == "charge":
        return billing_backend.do_J4(token, amount, card_expiration, billing_transaction_id)
    else:
        raise InvalidOperationError("Unknown action or billing: %s" % action)
    
def transaction_ok(request):
    # get passenger
    # create billing info and attach to passenger
    logging.info(request)
    return HttpResponse("\n".join([ "%s = %s" % t for t in request.GET.items()]))


def transaction_error(request):

    #report error
    logging.info(request)

    return HttpResponse("\n".join([ "%s = %s" % t for t in request.GET.items()]))
