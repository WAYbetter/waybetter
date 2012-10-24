var module = angular.module('wbControllers', ['wbServices', 'wbDefaults']);

module.controller("BookingCtrl", function ($scope, $q, $filter, BookingService, NotificationService, wbEvents, DefaultMessages, ASAP) {
    $scope.pickup = undefined;
    $scope.dropoff = undefined;

    $scope.has_luggage = false;
    $scope.is_private = false;
    $scope.num_seats = 1;

    $scope.pickup_dt = undefined; // Date instance or ASAP string
    $scope.pickup_date = undefined;
    $scope.pickup_time = undefined;
    $scope.pickup_datetime_default_idx =  0;
    $scope.pickup_datetime_options =  [];

    $scope.offers = [];
    $scope.selected_offer = undefined;
    $scope.private_price = undefined;
    $scope.booking_result = undefined;


    function join_date_and_time(date_dt, time_str) {
        if (time_str == ASAP){
            return ASAP;
        } else {
            var hours = time_str.split(":")[0];
            var minutes = time_str.split(":")[1];
            var result = new Date(date_dt);
            result.setHours(Number(hours));
            result.setMinutes(Number(minutes));

            return result;
        }
    }

    function booking_data(extra) {
        var data = {
            pickup:$scope.pickup,
            dropoff:$scope.dropoff,
            asap: !!($scope.pickup_dt == ASAP),
            pickup_dt: ($scope.pickup_dt == ASAP) ? undefined : $scope.pickup_dt.toUTCString(),
            settings:{
                num_seats:parseInt($scope.num_seats),
                private:$scope.is_private,
                luggage:$scope.has_luggage
            }
        };

        angular.extend(data, extra);
        return data;
    }

    function update_private_price() {
        if (!$scope.ready_to_order()) {
            return;
        }

        var booking_data = booking_data(({ private:true}));
        BookingService.get_private_offers(booking_data).then(function (private_offers) {
            if (private_offers && private_offers.length) {
                $scope.selected_offer = private_offers[0];
                $scope.private_price = $scope.selected_offer.price;
            } else {
                $scope.private_price = undefined;
            }

        }, function (message) {
            $scope.private_price = undefined;
            $scope.is_private = false;
            NotificationService.alert(message);
        });
    }

    $scope.sync = function () {
        BookingService.sync().then(function(data){
            $scope.ongoing_order_id = data.ongoing_order_id;
            $scope.future_orders_count = data.future_orders_count;
            $scope.pickup_datetime_default_idx = data.pickup_datetime_default_idx || 0;
            $scope.pickup_datetime_options = data.pickup_datetime_options.map(function(string_dt) {
                return new Date(string_dt);
            });
        }, function(){})
    };

    $scope.ready_to_order = function () {
        return $scope.pickup_dt && $scope.dropoff && $scope.dropoff.isValid() && $scope.pickup && $scope.pickup.isValid();
    };

    $scope.get_offers = function () {
        $scope.selected_offer = undefined;
        var offers_promise = BookingService.get_offers(booking_data());

        offers_promise.success(
            function (data) {
                if (data.offers) {
                    $scope.offers = data.offers;
                    console.log("got offers:", data);
                } else if (data.error) {
                    NotificationService.alert(data.error);
                }
            }).error(function () {
                NotificationService.alert(DefaultMessages.connection_error);
            });
    };

    $scope.book_ride = function () {
        $scope.booking_result = undefined;
        var ride_data = booking_data({ride_id:$scope.selected_offer.ride_id});

        var book_ride_promise = BookingService.book_ride(ride_data);
        book_ride_promise.then(function (booking_result) {
            console.log("book ride result: ", booking_result);
            $scope.booking_result = booking_result;

            var status = booking_result.status;
            var order_id = booking_result.order_id;
            if (status == 'success' && order_id) {

                // todo check order billing

            } else { // booking was not successful
                if (booking_result.redirect) {
                    // todo redirect
                } else if (status == 'auth_failed') {
                    // todo login
                } else {
                    // todo order failed
                }
            }
        }, function () { // booking request failed
            // todo order failed
            NotificationService.alert(DefaultMessages.connection_error);
        });
    };

    $scope.cancel_ride = function(ride) {
        // todo confirm
        BookingService.cancel_order(ride.order_id).then(function (message) {
            NotificationService.alert(message);
            $scope.get_next_rides();
        }, function (message) {
            NotificationService.alert(message);
        })
    };

    $scope.pickup_date_options = function() {
        var result = [];
        var date_strings = {};
        angular.forEach($scope.pickup_datetime_options, function(dt) {
            var date_string = dt.toDateString();
            if (! (date_string in date_strings)) {
                date_strings[date_string] = true;
                result.push(dt);
            }
        });

        return result;
    };

    $scope.pickup_time_options = function() {
        // return an array of strings [ASAP, "HH:MM"]
        var date_filter = $filter("date");
        if (! $scope.pickup_date) {
            return [];
        }

        var result = $scope.pickup_datetime_options.filter(function(dt) {
            return dt.toDateString() == $scope.pickup_date.toDateString();
        });

        result = result.map(function (dt) {
            return date_filter(dt, 'HH:mm');
        });

        // if today add ASAP
        if ((new Date()).toDateString() == $scope.pickup_date.toDateString()){
            result.unshift(ASAP);
        }

        return result;
    };


    // signals and watches
    $scope.$on(wbEvents.invalid_address, function(e, place) {
        console.log("invalid address", place);
    });

    $scope.$on(wbEvents.missing_hn, function(e, place_address, element) {
        console.log("missing_hn", place_address, element);
    });

    $scope.$watch('pickup', function (new_address) {
        if (new_address && new_address.isValid()) {
            $scope.map_controller.add_marker(new_address, {name:'pickup', icon: {url:'/static/images/pickup_marker.png', anchor: "bottom", width:35, height:40 }});
            $scope.map_controller.fit_markers();
        } else {
            $scope.map_controller.remove_marker('pickup');
        }
    });

    $scope.$watch('dropoff', function (new_address) {
        if (new_address && new_address.isValid()) {
            $scope.map_controller.add_marker(new_address, {name:'dropoff', icon: {url:'/static/images/dropoff_marker.png', anchor: "bottom",  width:35, height:40 }});
            $scope.map_controller.fit_markers();
        } else {
            $scope.map_controller.remove_marker('dropoff');
        }
    });

    $scope.$watch('pickup_datetime_options', function(dt_options) {
        var date_options = $scope.pickup_date_options();
        if (date_options.length) {
            var idx = 0;
            angular.forEach(date_options, function (dt, i) {
                if (dt.toDateString() == dt_options[$scope.pickup_datetime_default_idx].toDateString()){ // this is the default date
                    idx = i;
                }
            });
            $scope.pickup_date = date_options[idx];
        } else {
            $scope.pickup_date = undefined;
        }
    });

    $scope.$watch('pickup_date', function() {
        var time_options = $scope.pickup_time_options();
        if (time_options.length) {
            var idx = 0;

            var default_time_str = $filter("date")($scope.pickup_datetime_options[$scope.pickup_datetime_default_idx], "HH:mm");
            var idx_of_default = time_options.indexOf(default_time_str);
            if (idx_of_default > 0){
                idx = idx_of_default;
            }

            $scope.pickup_time = time_options[idx];
        } else {
            $scope.pickup_time = undefined;
        }
    });

    $scope.$watch(function() { return angular.toJson([$scope.pickup_date, $scope.pickup_time]) }, function() {
        if ($scope.pickup_date && $scope.pickup_time) {
            $scope.pickup_dt = join_date_and_time($scope.pickup_date, $scope.pickup_time);
            console.log("dt changed:", BookingService.pickup_dt);
        }
    });
});

