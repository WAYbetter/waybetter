var module = angular.module('wbGeoDirectives', ['wbGeoControllers', 'wbGeoServices', 'wbDefaults']);

module.directive("wbPac", function ($q, $timeout, PlacesService, wbEvents) {
    return {
        restrict:'A',
        link:function (scope, element, attrs) {
            var pac = new google.maps.places.Autocomplete(element[0], {});
            scope.$on(wbEvents.map_ready, function(e, map){
                pac.bindTo('bounds', map);
            });

            google.maps.event.addListener(pac, 'place_changed', function () {
                var place = pac.getPlace();
                scope.$emit(wbEvents.place_changed, place);

                scope[attrs.address] = undefined;

                scope.$apply(function () {
                    $q.when(PlacesService.get_valid_place(place, element.val()))
                        .then(function (result) {
                            var place_address = Address.fromGoogleResult(result.place);
                            if (result.valid) {
                                if (place_address.isValid()) {
                                    scope[attrs.address] = place_address;
                                } else {
                                    scope.$emit(wbEvents.invalid_address, place, attrs.address);
                                }
                            }
                            else if (result.missing_hn) {
                                scope.$emit(wbEvents.missing_hn, place_address, element, attrs.address);
                            }
                        },
                        function (status) {
                            scope.$emit(wbEvents.invalid_address, place, attrs.address);
                            console.log("WAYbetterLog: PlacesService.get_valid_place failed with status " + status);
                        });
                });
            });
        }
    }
});
module.directive("wbMap", function ($timeout, wbEvents) {
    return {
        restrict:'A',
        controller:'GoogleMapController',
        priority: 10,
        link:function (scope, element, attrs, controller) {
            var map = new google.maps.Map(element[0], {
                center:new google.maps.LatLng(32.064828,34.7764),
                mapTypeId:google.maps.MapTypeId.ROADMAP,
                panControl: false,
                mapTypeControl: false,
                streetViewControl: false,
                zoomControl: true,
                zoomControlOptions: {
                    style: google.maps.ZoomControlStyle.SMALL
                  },
                zoom:14
            });

            google.maps.event.addListener(map, 'click', function (e) {
                var lat = e.latLng.lat(),
                    lng = e.latLng.lng();

                scope.$emit(wbEvents.map_click, lat, lng);
            });

            controller.map = map;
            scope.map_controller = controller;
            scope.$emit(wbEvents.map_ready, map);
        }
    }
});


