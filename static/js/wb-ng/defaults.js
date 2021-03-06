var module = angular.module('wbDefaults', []);

module.constant('SupportPhone', "0722555442");
module.constant('HTTP_TIMEOUT', 15*1000);

var booking_continued = '/booking/continued/';
module.constant('DefaultURLS', {
    book_ride: '/book_ride/',
    cancel_order: '/cancel_order/',
    sync_app_state: "/sync_app_state/",

    get_offers: '/get_offers/',
    get_private_offers: '/get_private_offer/',
    get_order_billing_status: '/get_order_billing_status/',

    set_booking_data: '/booking/set_data/',

    booking_continued: booking_continued,
    update_picture: '/update_passenger_picture/',
    auth_failed_redirect: '/accounts/login/?next=' + booking_continued
});

module.constant('wbEvents', {
    map_ready: "map_ready",
    map_click: "map_click",
    place_changed: "place_changed",
    missing_hn: "missing_hn",
    invalid_address: "invalid_address"
});

module.constant('LivePersonDefaults', {
//    api_key:'049f04b5afaa4d8e9ce6edd30652ccde', // DEV
//    site_id:'P66808186' // DEV
    api_key:'3fa084abfee54a609d79df3c70bebe00', // PRODUCTION
    site_id:'9175100', // PRODUCTION
    server: 'server.iad.liveperson.net'
});
