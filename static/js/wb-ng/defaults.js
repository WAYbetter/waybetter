var module = angular.module('wbDefaults', []);

module.constant('SupportPhone', "0722555442");
module.constant('HTTP_TIMEOUT', 15*1000);
module.constant('ASAP', "ASAP");

module.constant('DefaultURLS', {
    book_ride: '/book_ride/',
    cancel_order: '/cancel_order/',
    sync_app_state: "/sync_app_state/",

    get_offers: '/get_offers/',
    get_private_offers: '/get_private_offer/',
    get_order_billing_status: '/get_order_billing_status/',

    auth_failed_redirect: '/registration/'
});
module.constant('DefaultMessages', {
        connection_error:'לא ניתן להשלים את הפעולה עקב שגיאה או בעיית חיבור לרשת',
        loading_offers_1: "מאתר נסיעות חופפות",
        loading_offers_2: "מחשב זמני נסיעה",
        loading_offers_3: "מעדכן מוניות",
        loading_book_ride: "Processing Order...",
        loading_private_offer: "Calculating private ride price",
        confirm_cancel_order: "",
        no_offers: "No matching rides found",

        book_existing_ride_txt: 'Join Ride',
        book_new_ride_txt: 'Start New Ride'
    }
);

module.constant('wbEvents', {
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
