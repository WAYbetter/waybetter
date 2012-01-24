from django.http import HttpResponse
from suds.client import Client
import logging

def authenticate(request):
    logging.getLogger('suds').setLevel(logging.ERROR)

    url = "http://81.218.41.97/xmlp_service/Taxi_Orders.asmx?wsdl"
    client = Client(url)
    logging.info(client)

    auth_number = client.service.Authenticate("waybetter", "l3mMbXbWNy7cHfHNHCG1SOpEI62b58Tv")
    logging.info(auth_number)
    return HttpResponse(auth_number)

