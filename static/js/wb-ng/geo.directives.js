var module = angular.module('wbGeoDirectives', ['wbGeoControllers', 'wbGeoServices']);

module.directive("wbPac", function ($q, $timeout, PlacesService, wbEvents) {
    return {
        restrict:'A',
        link:function (scope, element, attrs) {
            var pac = new google.maps.places.Autocomplete(element[0], {});

            google.maps.event.addListener(pac, 'place_changed', function () {
                var place = pac.getPlace();

                scope.$apply(function () {
                    $q.when(PlacesService.get_valid_place(place, element.val()))
                        .then(function (result) {
                            var place_address = Address.fromPlace(result.place);
                            if (result.valid) {
                                if (place_address.isValid()) {
                                    scope[attrs.address] = place_address;
                                } else {
                                    scope.$emit(wbEvents.invalid_address, place);
                                }
                            }
                            else if (result.missing_hn) {
                                scope.$emit(wbEvents.missing_hn, place_address, element);
                            }
                        },
                        function (status) {
                            scope.$emit(wbEvents.invalid_address, place);
                            console.log("WAYbetterLog: PlacesService.get_valid_place failed with status " + status);
                        });
                });
            });
        }
    }
});
module.directive("wbMap", function ($timeout) {
    return {
        restrict:'A',
        controller:'GoogleMapController',
        priority: 10,
        link:function (scope, element, attrs, controller) {
            controller.map = new google.maps.Map(element[0], {
                center:new google.maps.LatLng(32.064828,34.7764),
                mapTypeId:google.maps.MapTypeId.ROADMAP,
                panControl: false,
                mapTypeControl: false,
                zoomControl: false,
                streetViewControl: false,
                zoom:14
            });

            scope.map_controller = controller;
        }
    }
});


