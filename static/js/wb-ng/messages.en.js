var module = angular.module('wbMessages', []);

module.constant('ASAP', "ASAP");
module.constant('DefaultMessages', {
        today: "Today",
        or_less: "or less",
        pickup: "Pickup",
        available_seats: "Availabe Seats",
        you: "You",
        connection_error:'The operation could not be completed',
        loading_offers_1: "Searching for similar rides",
        loading_offers_2: "Computing ride duration",
        loading_offers_3: "Updating taxis",
        loading_book_ride: "Processing Order...",
        loading_private_offer: "Calculating private ride price",
        confirm_cancel_order: "",
        no_offers: "No matching rides found",

        book_existing_ride_txt: 'Join Ride',
        book_new_ride_txt: 'Start New Ride'
    }
);