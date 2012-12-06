var module = angular.module('wbGeoServices', []);

module.service("DirectionsService", function ($q) {
    var directionsService = new google.maps.DirectionsService();
    return {
        route:function (origin, destination) {
            var request = {
                origin:new google.maps.LatLng(origin.lat, origin.lng),
                destination:new google.maps.LatLng(destination.lat, destination.lng),
                travelMode:google.maps.TravelMode.DRIVING
            };

            var deffered = $q.defer();
            directionsService.route(request, function (result, status) {
                if (status == google.maps.DirectionsStatus.OK) {
                    deffered.resolve(result);
                } else {
                    deffered.reject(status);
                }
            });
            return deffered.promise;
        },
        estimate_time:function (origin, destination) {
            var deffered = $q.defer();
            this.route(origin, destination).then(function (result) {
                var duration = 0;
                angular.forEach(result.routes[0].legs, function (leg) {
                    duration += leg.duration.value;
                });
                deffered.resolve(duration);
            }, function (error_status) {
                deffered.reject(error_status);
            });

            return deffered.promise;
        }
    }
});

module.service("GeocodingService", function ($q, $rootScope) {
    var geocoder = new google.maps.Geocoder();
    return {
        _do_geocoding_request: function(request){
            var deferred = $q.defer();

            geocoder.geocode(request, function (result, status) {
                $rootScope.$apply(function() {
                    if (status == google.maps.GeocoderStatus.OK && result.length) {
                        deferred.resolve(result);
                    }
                    else {
                        deferred.reject(status);
                    }
                });
            });

            return deferred.promise;
        },
        geocode: function(address_string){
            return this._do_geocoding_request({
                address:address_string
            });
        },
        bulk_geocode: function(list_of_address_string){
            console.log("bulk geocode started");

            var defer = $q.defer(),
                results = [],
                completed = 0;

            angular.forEach(list_of_address_string, function(address_string, idx){
                geocoder.geocode({address: address_string}, function (result, status) {
                    completed++;
                    if (status == google.maps.GeocoderStatus.OK && result.length) {
                        console.log("bulk geocode #" + (idx+1) + " of " + list_of_address_string.length);
                        results[idx] = result;
                    } else {
                        console.log("bulk geocode #" + (idx+1) + " failed: " + status);
                        results[idx] = undefined;
                    }
                    if (list_of_address_string.length == completed) {
                        console.log("bulk geocode completed");
                        if ($rootScope.$$phase){
                            setTimeout(function(){  // $digest already in progress
                                console.log("exec delayed $apply");
                                $rootScope.$apply(defer.resolve(results));
                            }, 500)
                        } else {
                            $rootScope.$apply(defer.resolve(results));
                        }
                    }
                })
            });

            return defer.promise;
        },
        reverse_geocode: function(lat, lng){
            return this._do_geocoding_request({
                latLng:new google.maps.LatLng(lat, lng)
            });
        },
        reverse_geocode_resolve_range: function(lat, lng){
            var self = this;
            var defer = $q.defer();

            function get_address_candidates(place){
                var hn_component = get_address_component(place, 'street_number');
                var range = hn_component.long_name.split("-");
                var low = parseInt(range[0]);
                var high = parseInt(range[1]);

                var address_candidates = [];
                for (var i = low; i <= high; i += 2) {
                    var original_address = place.formatted_address;
                    var candidate = original_address.replace(hn_component.long_name, i);
                    address_candidates.push(candidate);
                }
                return address_candidates;
            }

            function get_closest(lat, lng, place_results){
                var place_latlon = new LatLon(lat, lng);
                // sort candidate by distance, closest will be first, undefined last
                place_results.sort(function (candidate1, candidate2) {
                    if (!candidate1) return 1
                    if (!candidate2) return -1

                    var location1 = candidate1.geometry.location;
                    var location2 = candidate2.geometry.location;
                    var d1 = new LatLon(location1.lat(), location1.lng()).distanceTo(place_latlon);
                    var d2 = new LatLon(location2.lat(), location2.lng()).distanceTo(place_latlon);

                    if (d1 < d2){
                        return -1
                    }
                    else{
                        return 1
                    }
                });
                return place_results[0];
            }

            this.reverse_geocode(lat, lng).then(function(result){
                var place = result[0];
                var hn_component = get_address_component(place, 'street_number');
                if (hn_component) {
                    var range = hn_component.long_name.split("-");
                    if (range.length == 2) {
                        var address_candidates = get_address_candidates(place);
                        var place_results = [];

                        // TODO bonus points: handle the case where some geocode requests fail
                        // by wrapping this section in another promise
                        angular.forEach(address_candidates, function (address, idx) {
                            self.geocode(address).then(function (result) {
                                var place = result[0];
//                                console.log("WAYbetterLog: candidte", idx, ":", address, "->", place);
                                place_results.push(place);
                                if (place_results.length == address_candidates.length){
                                    var closest = get_closest(lat, lng, place_results);
//                                    console.log("WAYbetterLog: last (", idx, ")", "resolving with", closest);
                                    defer.resolve(closest);
                                }
                            }, function reject(status) {
                                place_results.push(undefined)
                            });
                        });
                    }
                    else{
                        defer.resolve(place);
                    }
                }
                else{
                    defer.reject("No 'street_number' component found");
                }

            },
                function reject(status){
                    var err = {
                        msg: status,
                        lat: lat,
                        lng: lng
                    };
                    defer.reject(err);
                    console.log("WAYbetterLog: reject: " + status);
                });

            return defer.promise;
        }
    }
});

module.service("AutocompleteService", function ($q) {
    var service = new google.maps.places.AutocompleteService();

    return {
        get_predictions: function(string){
            var deferred = $q.defer();
            var query = {input: string};

            service.getQueryPredictions(query, function (result, status) {
                if (status == google.maps.GeocoderStatus.OK && result.length) {
                    deferred.resolve(result);
                }
                else {
                    deferred.reject(status);
                }
            });
            return deferred.promise;
        }
    }
});

module.service("PlacesService", function ($q, GeocodingService) {
    var REQUIRED_PROPERTIES = ["geometry", "address_components"],
        POI_TYPES = ["establishment", "train_station", "transit_station"];

    return {
        check_properties: function(place){
            var valid = true;
            angular.forEach(REQUIRED_PROPERTIES, function (prop) {
                if (!(prop in place)){
                    console.log("WAYbetterLog: required property missing: " + prop);
                    valid = false;
                }
            });
            return valid;
        },
        get_valid_place: function(place, user_input){
            /*
            * Check if place is valid for ordering.
            * if valid return an object as result.
            * if not valid, return a promise for reverse geocode to get a valid place
            * */
            var self = this;
            if (!this.check_properties(place)){
                return {valid: false};
            }

            var result = this.validate_place(place, user_input);
            if (result.valid || result.missing_hn){
                return result;
            }
            else{
                var defer = $q.defer();
                var promise = defer.promise;

                GeocodingService.reverse_geocode(place.geometry.location.lat(), place.geometry.location.lng()).then(
                    function (places) {
                        console.log("WAYbetterLog: reverse geocode results", places);
                        for (var i = 0; i < places.length; i++) {
                            var result_of_reverse = self.validate_place(places[i], user_input);
                            if (result_of_reverse.valid) {
                                defer.resolve(result_of_reverse);
                                break;
                            }
                        }
                        defer.reject();
                    },
                    function (status) {
                        defer.reject(status);
                    });

                return promise;
            }
        },
        validate_place: function(place, user_input){
            this.fix_place(place);

            var valid, poi, missing_hn;
            angular.forEach(place.types, function (type) {
                if (type == "street_address") valid = true; // a "street_address" is exempt from checking procedure
                if (type == "route") missing_hn = true; // a "route" is assumed to be missing a house number
                if (POI_TYPES.indexOf(type) > -1) {
                    poi = true;
                }
            });

            // handle cases where Google "guesses" a house number although the user entered only a street name
            if (!valid){
                var street_number_component = get_address_component(place, "street_number"),
                    route_component = get_address_component(place, "route");

                if (route_component && street_number_component) {
                    if (user_input && user_input.indexOf(route_component.short_name) == 0 && user_input.search(street_number_component.short_name) < 0) {
                        missing_hn = true;
                        console.log("WAYbetterLog: google generated house number");
                    } else {
                        valid = true;
                    }
                }
            }

            return {
                valid: valid,
                missing_hn: missing_hn,
                place: place,
                poi: poi
            }
        },

        fix_place: function(place){
            this.fix_house_number_range(place);
        },

        fix_house_number_range: function(place){
             // if house numbner is a range, take the middle house number
            var component = get_address_component(place, 'street_number');
            if (component) {
                var range = component.long_name.split("-");
                if (range.length == 2) {
                    var low = parseInt(range[0]);
                    var high = parseInt(range[1]);
                    var avg = parseInt((high + low) / 2);
                    component.short_name = avg;
                    place.formatted_address = place.formatted_address.replace(component.long_name, component.short_name);
                }
            }

        }
    }
});
