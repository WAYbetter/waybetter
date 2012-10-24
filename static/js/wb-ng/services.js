var module = angular.module('wbServices', ['wbDefaults']);

module.service('NotificationService', function () {});

module.service('HttpService', function ($http, $timeout, HTTP_TIMEOUT) {
    return {
        modalHttp:function (config, messages) {
            var messages_promises = [];
            angular.extend(config, {
                transformRequest:$http.defaults.transformRequest.concat(function (data) {
                    if (messages && messages.length){
                        angular.forEach(messages, function (message, i) {
                            var promise = $timeout(function(){
                                // todo show message
                            }, i*1500);
                            messages_promises.push(promise);
                        });
                    } else {
                        // todo show message
                    }

                    return data;
                }),
                transformResponse:$http.defaults.transformResponse.concat(function (data, headersGetter) {
                    if (messages_promises.length) {
                        angular.forEach(messages_promises, function (promise) {
                            $timeout.cancel(promise);
                            // todo hide message
                        });
                    } else {
                        // todo hide message
                    }

                    if (headersGetter()['content-type'] && headersGetter()['content-type'].indexOf("json") > -1) {
                        return angular.fromJson(data);
                    } else {
                        return data
                    }
                })
            });

            return this.http(config);
        },
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

module.service("BookingService", function ($q, HttpService, DefaultMessages, DefaultURLS) {
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
            return HttpService.modalHttp({
                method: 'GET',
                timeout: 60*1000,
                url: DefaultURLS.get_offers,
                params:{ data: ride_data}
            }, [DefaultMessages.offers_loading_1, DefaultMessages.offers_loading_2, DefaultMessages.offers_loading_3]);
        },

        book_ride:function (ride_data) {
            var defer = $q.defer();

            HttpService.modalHttp({
                method: 'POST',
                url: DefaultURLS.book_ride,
                data: {data: angular.toJson(ride_data)}
            }).then(function(result){
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

            HttpService.modalHttp({
                method:'POST',
                url: DefaultURLS.cancel_order,
                data:{order_id:order_id}
            }).success(function (response) {
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
            var config = {
                method:'GET',
                url:DefaultURLS.get_order_billing_status,
                params: {order_id: order_id}
            };
            return HttpService.http(config);
        },

        get_private_offers: function(ride_data) {
            var defer = $q.defer();

            var config = {
                method:'GET',
                url: DefaultURLS.get_private_offers,
                params: { data: ride_data }
            };

            DefaultURLS.modalHttp(config).success(function(response) {
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
