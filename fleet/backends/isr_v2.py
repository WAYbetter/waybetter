from django.contrib.auth.models import User
from ordering.models import Order
from suds.client import Client
import logging
import datetime

USERNAME = "waybetter"
PASSWORD = "l3mMbXbWNy7cHfHNHCG1SOpEI62b58Tv"

ISR_TESTER_EMAIL = "isr_tester@waybetter.com"

url = "http://mirs.isrcorp.co.il:1971/ISR_WCF_External_Gateway_Basic?wsdl"
client = Client(url)

#logging.getLogger('suds.client').setLevel(logging.DEBUG)
#logging.getLogger('suds.transport').setLevel(logging.DEBUG) # MUST BE THIS?
#logging.getLogger('suds.xsd.schema').setLevel(logging.DEBUG)
#logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)
#logging.getLogger('suds.resolver').setLevel(logging.DEBUG)
#logging.getLogger('suds.xsd.query').setLevel(logging.DEBUG)
#logging.getLogger('suds.xsd.basic').setLevel(logging.DEBUG)
#logging.getLogger('suds.binding.marshaller').setLevel(logging.DEBUG)

def _create_array_object(object_name):
    ns = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"
    return client.factory.create("{%s}%s" % (ns, object_name))

def _create_ISR_object(object_name):
    ns = "http://schemas.datacontract.org/2004/07/ISR_Objects"
    return client.factory.create("{%s}%s" % (ns, object_name))

def server_server_timestamp():
    return client.service.Server_Server_TimeStamp()

def server_server_version():
    return client.service.Server_Server_Version()

def server_session_id():
    return client.service.Server_Session_ID()

def server_test():
    return client.service.Server_Test()

def login():
    return client.service.Login(USERNAME, PASSWORD)

def _get_login_token():
    return "1qwe345tg"
#    login_response = login()
#    token = login_response['LoginResult']
#    return token

def _get_external_id(order):
    return order.id
#    return random.randrange(1000, 10000)

def _get_taxi_recommendation(order):
    max_radius = 1000
    max_vehicles = 2
    return client.service.Get_Taxi_Recommendation(_get_login_token(), float(order.from_lat), float(order.from_lon), max_radius, max_vehicles)

def get_taxi_recommendation():
    """
    for a random order
    """
    order = Order.get_one()
    return _get_taxi_recommendation(order)

def get_available_operators():
    token = _get_login_token()
    return client.service.Get_Available_Operators(token)

def _check_customer_login(username, password):
    return client.service.Check_Customer_Login(_get_login_token(), str(username), str(password))

def _get_customer_data(email, customer_id):
    return client.service.Get_Customer_Data(_get_login_token(), email, int(customer_id))

def get_external_order(order_id):
    return client.service.Get_External_Order(_get_login_token(), str(order_id))

def get_supplier_orders(supplier_id, status):
    return client.service.Get_Supplier_Orders(_get_login_token(), str(supplier_id), int(status))

def _create_passenger(passenger):
    isr_passenger = _create_ISR_object("Passanger")
    isr_passenger.Phone = passenger.phone
    isr_passenger.First_Name = passenger.name
    isr_passenger.Last_Name = "lastname"
    isr_passenger.Passanger_External_ID = passenger.id

    return isr_passenger

def _create_stop_address(order, type="from"):
    address_types = _create_ISR_object("Address_Types")
    stop_address = _create_ISR_object("Stop_Address")
    stop_address.Address_Type.value = address_types.Unknown # TODO: Normalized?
    stop_address.Full_Address = order.from_raw
    stop_address.Lat = order.from_lat
    stop_address.Lon = order.from_lon

    return stop_address

def _create_order_stop(order):
    order_stop = _create_ISR_object("Order_Stop")
    order_stop.Address = _create_stop_address(order)

    key_value_string_passenger = _create_array_object("KeyValueOfstringPassanger8pH_SfiQv")
    key_value_string_passenger.Key = 1 # the pickup order, same as Order_Stop.Stop_Order
    key_value_string_passenger.Value = _create_passenger(order.passenger)

    array_of_string_passenger = _create_array_object("ArrayOfKeyValueOfstringPassanger8pH_SfiQv")
    array_of_string_passenger.KeyValueOfstringPassanger8pH_SfiQv.append(key_value_string_passenger)

    order_stop.Passangers = array_of_string_passenger
    order_stop.Stop_Order = 1 # change when ISR supports more than 1 stop
    order_stop.Stop_Time = datetime.datetime.now().isoformat() # TODO: set order pickup time

    return order_stop

def _create_external_order(order):
    ex_order = _create_ISR_object("External_Order")
    ex_order.Auto_Order = True
    ex_order.Comments = order.comments
#    ex_order.Remarks = ""
    ex_order.Contact_Name = "waybetter"
    ex_order.Contact_Phone = "1234"
    ex_order.Customer = _create_customer_data(order.passenger)
    ex_order.External_Order_ID = _get_external_id(order)

    ex_order.Start_Time = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat() # TODO: set order pickup time
    ex_order.Finish_Time = (datetime.datetime.now() + datetime.timedelta(hours=2)).isoformat() # TODO: set order dropoff time

    order_stop = _create_order_stop(order)
    key_value_string_order_stop = _create_array_object("KeyValueOfstringOrder_Stop8pH_SfiQv")
    key_value_string_order_stop.Key = 1 # the pickup order, same as Order_Stop.Stop_Order
    key_value_string_order_stop.Value = order_stop

    array_of_string_order_stop = _create_array_object("ArrayOfKeyValueOfstringOrder_Stop8pH_SfiQv")
    array_of_string_order_stop.KeyValueOfstringOrder_Stop8pH_SfiQv.append(key_value_string_order_stop)
    ex_order.Stops = array_of_string_order_stop

    order_type = _create_ISR_object("External_Order.Order_Type")
    ex_order.Order_Type.value = order_type.Taxi_Order

    order_status = _create_ISR_object("External_Order.Status")
    ex_order.Status.value = order_status.Waiting_for_passenger # doesn't matter
    return ex_order

def _insert_external_order(order):
    ex_order = _create_external_order(order)
    return client.service.Insert_External_Order(_get_login_token(), ex_order)

def insert_external_order():
    order = None
    for order in Order.objects.filter(debug=True):
        if order.passenger:
            break

    return _insert_external_order(order)

def cancel_order(order_id):
    order = Order.by_id(order_id)
    external_order_id = _get_external_id(order)
    reply = client.service.Cancel_Order(_get_login_token(), str(external_order_id))
    return reply

def get_external_order(order_id):
    order = Order.by_id(order_id)
    external_order_id = _get_external_id(order)
    reply = client.service.Get_External_Order(_get_login_token(), str(external_order_id))
    return reply

def get_order_status(order_id):
    status = None
    reply = get_external_order(order_id)
    if reply.External_Order_ID == order_id:
        status = reply.Get_External_OrderResult.Status

    return status

def _create_customer_data(passenger):
    # TODO_WB: if passenger.business
    customer_data = _create_ISR_object("Customer_Data")
    customer_data.Cell_phone = passenger.phone
    customer_data.Phone = passenger.phone
    customer_data.Name = passenger.full_name
    return customer_data

def _insert_customer(passenger):
    cd = _create_customer_data(passenger)
    return client.service.Insert_Customer(_get_login_token(), cd)

def _insert_customer():
    """
    Create a customer from ISR user
    """
    try:
        user = User.objects.get(email=ISR_TESTER_EMAIL)
#        user = User.objects.get(email="amir@waybetter.com")
    except:
        user = None
    if user and user.passenger:
        return _insert_customer(user.passenger)
    else:
        return "ISR user not found (%s)" % ISR_TESTER_EMAIL
