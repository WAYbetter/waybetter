import logging
from fleet.models import AbstractFleetManagerBackend, FleetManagerRide, FleetManagerRideStatus
from common.suds_appengine import GAEClient
from common.tz_support import default_tz_now
import datetime

DEFAULT_TIMEDELTA = datetime.timedelta(minutes=5)

WAYBETTER_STATUS_MAP = {
    'Recived_In_Server': FleetManagerRideStatus.PENDING,
    'Start_ticket_execution': FleetManagerRideStatus.PENDING,
    'En_route_to_next_passenger': FleetManagerRideStatus.ASSIGNED_TO_TAXI,
    'Passenger_On_vehicle': FleetManagerRideStatus.PASSENGER_PICKUP,
    'Passenger_No_show': FleetManagerRideStatus.PASSENGER_NO_SHOW,
    'Opertation_cancellation': FleetManagerRideStatus.CANCELLED,
    'Waiting_for_passenger': FleetManagerRideStatus.ASSIGNED_TO_TAXI,
    'Passenger_delivered_at_Location': FleetManagerRideStatus.PASSENGER_DROPOFF,
    'End_Ticket_Execution': FleetManagerRideStatus.COMPLETED,
    'Future_Execution': FleetManagerRideStatus.PENDING,
    'Future_Execution_With_Vehicle': FleetManagerRideStatus.PENDING,
    'Waiting_For_Driver_Acception': FleetManagerRideStatus.PENDING,
    'Driver_Cancellation': FleetManagerRideStatus.PENDING,
    'No_Avaliable_Vehicles': FleetManagerRideStatus.PENDING
}

INITIAL_STATUS = 'Recived_In_Server' # should map to FleetManagerOrderStatus.PENDING

class ISR(AbstractFleetManagerBackend):
    USERNAME = "***REMOVED***"
    PASSWORD = "***REMOVED***"

    _url = "***REMOVED***"
    _client = None
    _supplier_id = None

    @classmethod
    def create_ride(cls, ride, station, taxi_number=None):
        order = ride.orders.all()[0]
        order.id = ride.id

        ex_order = cls._create_external_order(order, station.fleet_station_id)
        reply = cls._get_client().service.Insert_External_Order(cls._get_login_token(), ex_order)
        if reply:
            fmr = cls._create_fmr(reply.Insert_External_OrderResult)
            return fmr

        return None

    @classmethod
    def cancel_ride(cls, ride_id):
        cls._get_client().service.Cancel_Order(cls._get_login_token(), ride_id)
        return True # ISRsays: this call never fails thus returns nothing

    @classmethod
    def get_ride(cls, ride_id):
        reply = cls._get_client().service.Get_External_Order(cls._get_login_token(), ride_id)
        if reply:
            fmr = cls._create_fmr(reply.Get_External_OrderResult)
            return fmr

        return None

    @classmethod
    def _get_rides_by_status(cls, status_list):
        array_of_int = cls._create_array_object("ArrayOfint")
        array_of_int.int = status_list
        reply = cls._get_client().service.Get_VAR_Supplier_Orders(cls._get_login_token(), cls._get_supplier_id(), array_of_int)

        ex_orders = getattr(reply.Get_VAR_Supplier_OrdersResult, "External_Order", [])
        fmrs = [cls._create_fmr(ex_order) for ex_order in ex_orders]
        return fmrs

    @classmethod
    def _create_fmr(cls, ex_order):
        id = ex_order.External_Order_ID
        status = WAYBETTER_STATUS_MAP.get(ex_order.Status)
        taxi_id = ex_order.Operating_Vehicle

        lat, lon, timestamp = None, None, None
        if ex_order.Operating_Vehicle_Poistion is not None:
            lat = ex_order.Operating_Vehicle_Poistion.Lat
            lon = ex_order.Operating_Vehicle_Poistion.Lon
            timestamp = ex_order.Operating_Vehicle_Poistion.Insert_Time_Stamp
#            timestamp = ex_order.Operating_Vehicle_Poistion.SPM_Time_Stamp

        return FleetManagerRide(id, status, taxi_id, None, lat, lon, timestamp, raw_status=ex_order.Status)

    @classmethod
    def _create_external_order(cls, order, isr_station_id):
        ex_order = cls._create_ISR_object("External_Order")
        ex_order.Auto_Order = True #ISRsays: should be True
        ex_order.Comments = order.comments
        ex_order.Remarks = ""
        ex_order.Visa_ID = "visa_id"
        ex_order.Customer = cls._create_customer_data(order.passenger)
        ex_order.External_Order_ID = order.id
        ex_order.Prefered_Operator_ID = isr_station_id
        # ex_order.Prefered_Vehicle_ID = -1

        # TODO_WB: if passenger.business the business is contact?
        ex_order.Contact_Name = ""
        ex_order.Contact_Phone = ""

        # ISRsays: these fields are required but not reflected in ISR client UI
        start_time = default_tz_now() + DEFAULT_TIMEDELTA
        finish_time = start_time + DEFAULT_TIMEDELTA
        ex_order.Start_Time = (order.depart_time or start_time).isoformat()
        ex_order.Finish_Time = (order.arrive_time or finish_time).isoformat()

        order_stop = cls._create_order_stop(order)
        key_value_string_order_stop = cls._create_array_object("KeyValueOfstringOrder_Stop8pH_SfiQv")
        key_value_string_order_stop.Key = order_stop.Stop_Order
        key_value_string_order_stop.Value = order_stop

        array_of_string_order_stop = cls._create_array_object("ArrayOfKeyValueOfstringOrder_Stop8pH_SfiQv")
        array_of_string_order_stop.KeyValueOfstringOrder_Stop8pH_SfiQv.append(key_value_string_order_stop)
        ex_order.Stops = array_of_string_order_stop

        order_type = cls._create_ISR_object("External_Order.Order_Type")
        ex_order.Order_Type.value = order_type.Taxi_Order

        order_status = cls._create_ISR_object("External_Order.Status")
        ex_order.Status.value = getattr(order_status, INITIAL_STATUS)
        return ex_order

    @classmethod
    def _create_customer_data(cls, passenger):
        # TODO_WB: if passenger.business the business is customer?
        customer_data = cls._create_ISR_object("Customer_Data")
        customer_data.Cell_phone = passenger.phone
        customer_data.Phone = passenger.phone
        customer_data.Name = passenger.full_name
        return customer_data

    @classmethod
    def _create_order_stop(cls, order):
        order_stop = cls._create_ISR_object("Order_Stop")
        order_stop.Address = cls._create_stop_address(order)

        stop_number = 0 # TODO_WB: the pickup order, change when ISR supports more than 1 stop

        key_value_string_passenger = cls._create_array_object("KeyValueOfstringPassanger8pH_SfiQv")
        key_value_string_passenger.Key = stop_number
        key_value_string_passenger.Value = cls._create_passenger(order.passenger)

        array_of_string_passenger = cls._create_array_object("ArrayOfKeyValueOfstringPassanger8pH_SfiQv")
        array_of_string_passenger.KeyValueOfstringPassanger8pH_SfiQv.append(key_value_string_passenger)

        order_stop.Passangers = array_of_string_passenger
        order_stop.Stop_Order = stop_number

        # this field is used as the start time in ISR client UI
        order_stop.Stop_Time = (order.depart_time or (default_tz_now() + DEFAULT_TIMEDELTA)).isoformat()

        return order_stop

    @classmethod
    def _create_stop_address(cls, order, type="from"):
        address_types = cls._create_ISR_object("Address_Types")
        stop_address = cls._create_ISR_object("Stop_Address")
        stop_address.Address_Type.value = address_types.Unknown # TODO: Normalized?
        stop_address.Full_Address = getattr(order, "%s_raw" % type)
        city = getattr(order, "%s_city" % type)
        stop_address.City = city.name if city else ""
        stop_address.Street = getattr(order, "%s_street_address" % type)
        stop_address.House = getattr(order, "%s_house_number" % type)
        stop_address.Lat = getattr(order, "%s_lat" % type)
        stop_address.Lon = getattr(order, "%s_lon" % type)
#        stop_address.Poi = ""

        return stop_address

    @classmethod
    def _create_passenger(cls, passenger):
        isr_passenger = cls._create_ISR_object("Passanger")
        isr_passenger.Phone = passenger.phone
        isr_passenger.First_Name = passenger.full_name
        isr_passenger.Last_Name = ""
        isr_passenger.Passanger_External_ID = passenger.id

        return isr_passenger

    @classmethod
    def _get_client(cls):
        if cls._client is None:
#            from suds.transport.http import HttpAuthenticated
#            t = HttpAuthenticated(username=cls.USERNAME, password=cls.PASSWORD)
#            cls._client = GAEClient(cls._url, transport=t)

            cls._client = GAEClient(cls._url)
            logging.info("created ISR client")

        return cls._client

    @classmethod
    def _get_supplier_id(cls):
        if cls._supplier_id is None:
            reply = cls._get_client().service.Get_Supplier_ID(cls._get_login_token())
            if reply:
                cls._supplier_id = reply.Get_Supplier_IDResult

        return cls._supplier_id

    @classmethod
    def _get_login_token(cls):
        # return "1qwe345tg"
        login_response = cls._get_client().service.Login(cls.USERNAME, cls.PASSWORD)
        token = login_response['LoginResult']
        return token

    @classmethod
    def _create_array_object(cls, object_name):
        ns = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"
        return cls._get_client().factory.create("{%s}%s" % (ns, object_name))

    @classmethod
    def _create_ISR_object(cls, object_name):
        ns = "http://schemas.datacontract.org/2004/07/ISR_Objects"
        return cls._get_client().factory.create("{%s}%s" % (ns, object_name))