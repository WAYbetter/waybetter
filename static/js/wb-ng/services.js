var module = angular.module('wbServices', ['wbDefaults', 'wbMessages']);

module.service('NotificationService', function () {
    return {
        alert: function(m){
            alert(m);
        },
        confirm: function(m){
            return window.confirm(m);
        }
    }
});

module.service('HttpService', function ($http, $timeout, HTTP_TIMEOUT) {
    return {
        http: function(config) {
            config = config || {};
            config.timeout = config.timeout || HTTP_TIMEOUT;

            return $http(config);
        },
        http_get:function (url, config) {
            config = config || {};
            config.timeout = config.timeout || HTTP_TIMEOUT;

            return $http.get(url, config)
        },
        http_post:function (url, data, config) {
            config = config || {};
            config.timeout = config.timeout || HTTP_TIMEOUT;

            return $http.post(url, data, config)
        }
    }
});

module.service("BookingService", function ($q, $timeout, HttpService, DefaultMessages, DefaultURLS) {
    return {
        sync: function(){
            var defer = $q.defer();
            HttpService.http_get(DefaultURLS.sync_app_state).success(function (data) {
                console.log("sync success");
                defer.resolve(data);
            }).error(function(error, status_code) {
                console.log("sync_state error:" + error);
                defer.reject();
            });

            return defer.promise;
        },

        get_offers:function (ride_data) {
            return HttpService.http_get(DefaultURLS.get_offers, {params: {data: ride_data}, timeout: 60*1000 });
        },

        book_ride:function (ride_data) {
            var defer = $q.defer();

            HttpService.http_post(DefaultURLS.book_ride, {data: angular.toJson(ride_data)})
                .then(function(result){
                    var booking_result = result.data;
                    if (result.data && result.data.pickup_dt){
                        booking_result.pickup_dt = new Date(result.data.pickup_dt);
                    }
                    defer.resolve(booking_result);
                },
                function(){
                    defer.reject(DefaultMessages.connection_error);
            });

            return defer.promise;
        },

        cancel_order: function(order_id) {
            var result_deferred = $q.defer();

            HttpService.http_post(DefaultURLS.cancel_order, jQuery.param({order_id:order_id}))
                .success(function (response) {
                    if (response.success) {
                        result_deferred.resolve(response.message);
                    } else {
                        result_deferred.reject(response.message);
                    }
                }).error(function () {
                    result_deferred.reject(DefaultMessages.connection_error);
                });
                return result_deferred.promise;
        },

        get_order_billing_status: function(order_id) {
            var defer = $q.defer();
            var config = {
                params: {order_id: order_id}
            };

            function poll_server() {
                console.log("polling server for billing status:", order_id);
                HttpService.http_get(DefaultURLS.get_order_billing_status, config).success(
                    function (data) {
                        if (data.status == "pending") {
                            $timeout(poll_server, 3000)
                        } else if (data.status == "approved") {
                            defer.resolve("ok");
                        } else {
                            console.log("rejecting check_order_billing: " + data.status);
                            defer.reject(data.status);
                        }
                    }).error(function (error, status) {
                        console.log("check_order_billing failed: " + error + ", " + status);
                        // retry
                        $timeout(poll_server, 3000);
                    });
            }

            poll_server();
            return defer.promise;
        },

        get_private_offers: function(ride_data) {
            var defer = $q.defer();

            HttpService.http_get(DefaultURLS.get_private_offers, {params: { data: ride_data }}).success(function(response) {
                if (response.offers){
                    defer.resolve(response.offers);
                } else {
                    console.log("no private offers returned");
                    defer.reject(DefaultMessages.no_offers);
                }
            }).error(function() {
                console.log("error getting private offers");
                defer.reject(DefaultMessages.connection_error);
            });

            return defer.promise;
        }
    };
});
