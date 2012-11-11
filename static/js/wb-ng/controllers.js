var module = angular.module('wbControllers', ['wbServices', 'wbDefaults', 'wbMessages']);

module.controller("BookingCtrl", function ($scope, $q, $filter, $timeout, BookingService, NotificationService, wbEvents, DefaultMessages, DefaultURLS, ASAP) {
    $scope.continuing = false;  // continuing booking an order after login/registration
    $scope.loading = false;
    $scope.logged_in = false;
    $scope.passenger_picture_url = undefined;

    $scope.pickup = undefined;
    $scope.dropoff = undefined;
    $scope.pickup_error = undefined;
    $scope.dropoff_error = undefined;

//    $scope.pickup = Address.fromJSON('{"street":"אלנבי","house_number":"1","city_name":"תל אביב יפו","country_code":"IL","lat":32.0736683,"lng":34.76546570000005}');
//    $scope.dropoff = Address.fromJSON('{"street":"מרגולין","house_number":"1","city_name":"תל אביב יפו","country_code":"IL","lat":32.0586624,"lng":34.78742}');

    $scope.has_luggage = false;
    $scope.is_private = false;
    $scope.num_seats = 1;

    $scope.pickup_dt = undefined; // Date instance or ASAP string
    $scope.pickup_date = undefined;
    $scope.pickup_time = undefined;
    $scope.pickup_datetime_default_idx =  0;
    $scope.pickup_datetime_options =  [];

    $scope.offers = [];
//    $scope.offers = [{"new_ride":true,"comment":"","price":46,"pickup_time":1351172420000,"seats_left":3}];
    $scope.selected_offer = undefined;
    $scope.private_price = undefined;
    $scope.booking_result = undefined;
    $scope.booking_approved = undefined;
    $scope.booking_error = undefined;

    $scope.ASAP = ASAP;

    $scope.loading_message = "";

    function set_loading_message(m){
        $scope.loading = true;
        $scope.loading_message = m;
    }
    function clear_loading_message(){
        $scope.loading = false;
        $scope.loading_message = "";
    }

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

    function get_booking_data(extra) {
        var data = {
            pickup:$scope.pickup,
            dropoff:$scope.dropoff,
            asap: !!($scope.pickup_dt == ASAP),
            pickup_dt: ($scope.pickup_dt == ASAP) ? undefined : $scope.pickup_dt.toUTCString(),
            settings:{
                num_seats:parseInt($scope.num_seats),
                private:$scope.is_private,
                luggage:$scope.has_luggage
            },

            // will be stored in session to capture current booking
            offers: $scope.offers,
            selected_offer: $scope.selected_offer
        };

        angular.extend(data, extra);
        return data;
    }

    function update_private_price() {
        if (!$scope.ready_to_order()) {
            return;
        }

        set_loading_message(DefaultMessages.loading_private_offer);
        var booking_data = get_booking_data({ private:true });
        BookingService.get_private_offers(booking_data).then(function (private_offers) {
            clear_loading_message();
            if (private_offers && private_offers.length) {
                $scope.selected_offer = private_offers[0];
                $scope.private_price = $scope.selected_offer.price;
            } else {
                $scope.private_price = undefined;
            }

        }, function (message) {
            clear_loading_message();
            $scope.private_price = undefined;
            $scope.is_private = false;
            $scope.booking_error = message;
        });
    }

    $scope.sync = function (continue_booking) {
        BookingService.sync().then(function(data){
            $scope.logged_in = data.logged_in;
            $scope.passenger_picture_url = data.passenger_picture_url;

            if (!continue_booking) {
                // populating datetime options triggers a watch that sets pickup_dt
                // but when booking continues we use the server's pickup_dt instead of what the watch sets

                $scope.pickup_datetime_default_idx = data.pickup_datetime_default_idx || 0;
                $scope.pickup_datetime_options = data.pickup_datetime_options.map(function (string_dt) {
                    return new Date(string_dt);
                });
            }

            if (continue_booking && data.booking_data){ // continue an interrupted booking process
                $scope.continuing = true;

                console.log("booking continued", data.booking_data);

                var booking_data = angular.fromJson(data.booking_data);

                $scope.pickup = Address.fromJSON(booking_data.pickup);
                $scope.dropoff = Address.fromJSON(booking_data.dropoff);
                $scope.pickup_dt = booking_data.asap ? ASAP :  new Date(booking_data.pickup_dt);
                $scope.num_seats = booking_data.settings.num_seats;
                $scope.is_private = booking_data.settings.private;
                $scope.has_luggage = booking_data.settings.luggage;

                $scope.offers = booking_data.offers;
                $scope.selected_offer = booking_data.selected_offer;

                if ($scope.ready_to_order()){
                    $scope.book_ride();
                }
            }
        }, angular.noop)
    };

    $scope.reset = function(){
        $scope.offers = [];
        $scope.selected_offer = undefined;
        $scope.private_price = undefined;
        $scope.booking_result = undefined;
        $scope.booking_approved = undefined;
        $scope.booking_error = undefined;
    };

    $scope.ready_to_order = function () {
        return $scope.pickup_dt && $scope.dropoff && $scope.dropoff.isValid() && $scope.pickup && $scope.pickup.isValid();
    };

    $scope.get_offers = function () {
        $scope.selected_offer = undefined;
        var offers_promise = BookingService.get_offers(get_booking_data());

        offers_promise.success(
            function (data) {
                clear_messages();
                if (data.offers) {
                    $scope.offers = data.offers;
                    console.log("got offers:", data);
                    if ($scope.offers.length == 1) {  // no rides to join
                        $scope.choose_offer($scope.offers[0]);
                    }
                } else if (data.error) {
                    NotificationService.alert(data.error);
                }
            }).error(function () {
                clear_messages();
                NotificationService.alert(DefaultMessages.connection_error);
            });


        var messages = [DefaultMessages.loading_offers_1, DefaultMessages.loading_offers_2, DefaultMessages.loading_offers_3];
        var promises = [];
        angular.forEach(messages, function (m, i) {
            var promise = $timeout(function () {
                set_loading_message(m);
            }, i * 1500);
            promises.push(promise);
        });
        function clear_messages(){
            clear_loading_message();
            angular.forEach(promises, function (promise) {
                $timeout.cancel(promise);
            });
        }
    };

    $scope.book_ride = function () {
        $scope.booking_result = undefined;
        $scope.booking_error = undefined;
        set_loading_message(DefaultMessages.loading_book_ride);

        var ride_data = get_booking_data({ride_id:$scope.selected_offer.ride_id});
        BookingService.book_ride(ride_data).then(function (booking_result) {
            console.log("book ride result: ", booking_result);
            $scope.booking_result = booking_result;

            var status = booking_result.status;
            var order_id = booking_result.order_id;
            if (status == 'success' && order_id) {
                set_loading_message(DefaultMessages.loading_billing);
                BookingService.get_order_billing_status(order_id).then(function() {
                        clear_loading_message();
                        $scope.booking_approved = true;
                    }, function(error) {
                        clear_loading_message();
                        $scope.booking_approved = false;
                        $scope.booking_error = DefaultMessages.billing_error;
                    });
            } else { // booking was not successful
                clear_loading_message();
                if (booking_result.redirect) {
                    window.location.href = booking_result.redirect;
                } else if (status == 'auth_failed') {
                    window.location.href = DefaultURLS.auth_failed_redirect;
                } else {
                    $scope.booking_error = booking_result.error || DefaultMessages.connection_error;
                }
            }
        }, function () { // booking request failed
            // todo order failed
            $scope.booking_error = DefaultMessages.connection_error;
            clear_loading_message();
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

    $scope.new_ride_offers = function() {
        return $filter('filter')($scope.offers, {new_ride: true});
    };

    $scope.existing_ride_offers = function() {
        return $filter('filter')($scope.offers, {new_ride: false});
    };

    $scope.choose_offer = function (offer) {
        if ($scope.loading){
            return;
        }

        if ($scope.selected_offer != offer) {
            $scope.selected_offer = offer;
        } else {
            $scope.selected_offer = undefined;
        }
    };

    $scope.update_picture = function(){
        // todo
    };

    // signals and watches
    $scope.$on(wbEvents.invalid_address, function(e, place, input_type) {
        console.log("invalid address", place);
        $scope[input_type + "_error"] = DefaultMessages.unknown_address;
    });

    $scope.$on(wbEvents.missing_hn, function(e, place_address, element, input_type) {
        console.log("missing_hn", place_address, element);
        $scope[input_type + "_error"] = DefaultMessages.missing_house_number;
    });

    $scope.$watch('pickup', function (new_address) {
        $scope.pickup_error = false;
        if (new_address && new_address.isValid()) {
            $scope.map_controller.add_marker(new_address, {name:'pickup', icon: {url:'/static/images/pickup_marker.png', anchor: "bottom", width:35, height:40 }});
            $scope.map_controller.fit_markers();
        } else {
            $scope.map_controller.remove_marker('pickup');
        }
    });

    $scope.$watch('dropoff', function (new_address) {
        $scope.dropoff_error = false;
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
            console.log("dt changed:", $scope.pickup_dt);
        }
    });

    $scope.$watch('is_private', function(new_val, old_val) {
        if (!new_val) {
            $scope.private_price = undefined;
        }
    });

    $scope.$watch(function() {return angular.toJson([$scope.pickup_dt, $scope.is_private, $scope.pickup, $scope.dropoff])}, function() {
        if ($scope.is_private && !$scope.continuing) {
            update_private_price();
        }
    });

});

