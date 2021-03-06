var module = angular.module('wbMessages', []);

module.constant('ASAP', "ASAP");
module.constant('DefaultMessages', {
        today: "Today",
        or_less: "or less",
        pickup: "Pickup",
        pickup_address: "pickup address",
        dropoff_address: "dropoff address",
        available_seats: "Availabe Seats",
        new_taxi: "New Taxi",
        you: "You",
        private_ride: "Private Ride",
        connection_error:'The operation could not be completed',
        billing_error:'Billing was not approved',
        loading_offers_1: "Searching for similar rides",
        loading_offers_2: "Computing ride duration",
        loading_offers_3: "Updating taxis",
        loading_book_ride: "Processing order",
        loading_billing: "Processing billing",
        loading_private_offer: "Calculating private ride price",
        loading_update_picture: "Redirecting to Facebook",
        no_offers: "No matching rides found",

        missing_house_number: "missing house number",
        unknown_address: "unknown address",

        book_existing_ride_txt: 'Join Ride',
        book_new_ride_txt: 'Start New Ride',
        confirm_cancel_order: "Really cancel order?",
        cancel_ride: 'Cancel Ride',
        report_ride: 'Report Ride'
    }
);