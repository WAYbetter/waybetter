var module = angular.module('wbDirectives', ['wbMessages', 'wbFilters']);

module.directive("wbCounter", function () {
    return {
        restrict:'E',
        scope:{
            value:"@"
        },
        replace:true,
        link:function (scope, element, attrs) {
            function render() {
                var container = "<div class='ticker-container'>{0}</div>";
                var inner = "";
                var parts = scope.value ? scope.value.toString().split("") : [];
                for (var i = 0; i < parts.length; i++) {
                    inner += "<div class='ticker-item'>{0}</div>".format(parts[i]);
                }
                element.html(container.format(inner));
            }

            console.log(scope);
            scope.$watch("value", function () {
                console.log("value changed = " + scope.value);
                render();
            });
        }
    }
});

module.directive("myRide", function (DefaultMessages) {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="ride row-fluid"> \
                <div class="ride-passengers span4"> \
                    <div class="type-indicator"></div>\
                    <ride-pics-for-my-ride></ride-pics-for-my-ride> \
                </div> \
                <div class="ride-pickup-details span4"> \
                    <strong>' + DefaultMessages.pickup +  ': (( ride.pickup_time | wb_date:"EEE d/M" )) ((  ride.pickup_time | date:"H:mm" ))</strong> \
                    <div ng-hide="ride.is_private">(( ride.seats_left )) ' + DefaultMessages.available_seats + '</div> \
                    <div ng-show="ride.is_private">' + DefaultMessages.private_ride + '</div> \
                </div> \
                <div class="ride-price-details span4"> \
                    <strong class="price">(( ride.price | currency:"₪" ))</strong> \
                    <div>(( ride.billing_status ))</div> \
                </div> \
            </div>'
    }
});
module.directive("myRideAction", function (DefaultMessages) {
    return {
        restrict: 'E',
        compile: function(element, attrs){
            var action = attrs.action;
            var action_btn_html = (action == "cancel") ?
                '<button class="btn btn-danger btn-block btn-large" ng-click="cancel_ride(ride)">' + DefaultMessages.cancel_ride +' </button>' :
                '<button class="btn btn-danger btn-block btn-large" ng-click="report_ride(ride)">' + DefaultMessages.report_ride +' </button>' ;

            var html_text =
                '<div class="ride-action row-fluid">' +
                    '<div class="ride-comment span8" ng-show="ride.comment">(( ride.comment ))</div>' +
                    '<div class="span4 pull-right">' + action_btn_html + '</div>' +
                    '<div class="clearfix"></div>' +
                '</div>';

            element.replaceWith(html_text);
        }
    }
});


module.directive("offer", function (DefaultMessages, ASAP) {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="ride row-fluid"> \
                <div class="ride-passengers span5"> \
                    <div class="type-indicator"></div>\
                    <ride-pics-for-offer></ride-pics-for-offer> \
                </div> \
                <div class="ride-pickup-details span4"> \
                    <div ng-switch on="offer.new_ride && pickup_dt == ASAP" class="time">\
                        <strong ng-switch-when="false">' + DefaultMessages.pickup +  ': (( offer.pickup_time | wb_date:"EEE d/M" )) ((  offer.pickup_time | date:"H:mm" ))</strong> \
                        <strong ng-switch-when="true">' + DefaultMessages.pickup +  ': ' + (( ASAP )) + '</strong> \
                    </div>\
                    <div ng-switch on="offer.new_ride">\
                        <div ng-switch-when="false">(( offer.seats_left )) ' + DefaultMessages.available_seats + '</div> \
                        <div ng-switch-when="true">' + DefaultMessages.new_taxi + '</div> \
                    </div>\
                </div> \
                <div class="ride-price-details span3"> \
                    <strong class="price">(( offer.price | currency:"₪" ))</strong> \
                    <div>' + DefaultMessages.or_less + '</span> \
                </div> \
            </div>'
    }
});
module.directive("offerAction", function (DefaultMessages) {
    return {
        restrict: 'E',
        compile: function(element, attrs){
            var action_text = attrs.type == "existing" ? DefaultMessages.book_existing_ride_txt : DefaultMessages.book_new_ride_txt;
            var html_text = '<div class="ride-action row-fluid">' +
                                '<div class="ride-comment span8" ng-show="offer.comment">(( offer.comment ))</div>' +
                                '<div class="span4 pull-right"><button class="btn btn-warning btn-block btn-large" ng-click="book_ride()" ng-disabled="loading">' + action_text +' </button></div>' +
                                '<div class="clearfix"></div>' +
                            '</div>';
            element.replaceWith(html_text);
        }
    }
});


module.directive("rideSep", function () {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="ride-sep"> \
                <table> \
                    <tr> \
                        <td class="shadow-l"></td> \
                        <td class="shadow-m"></td> \
                        <td class="shadow-r"></td> \
                    </tr> \
                </table> \
            </div> \
        '
    }
});
module.directive("ridePicsForOffer", function () {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="ride-pics"> \
                <ride-pics-passenger ng-repeat="passenger in offer.passengers"></ride-pics-passenger> \
                <ride-pics-you ng-repeat="x in [] | range:num_seats"> </ride-pics-you>\
                <ride-pics-seat ng-repeat="x in [] | range:offer.seats_left - num_seats"></ride-pics-seat>\
            </div> \
        '
    }
});
module.directive("ridePicsForMyRide", function () {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="ride-pics"> \
                <ride-pics-passenger ng-repeat="passenger in ride.passengers"></ride-pics-passenger> \
                <ride-pics-you ng-repeat="x in [] | range:ride.your_seats"> </ride-pics-you>\
                <ride-pics-seat ng-repeat="x in [] | range:ride.seats_left"></ride-pics-seat>\
            </div> \
        '
    }
});
module.directive("ridePicsYou", function (DefaultMessages) {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="ride-pics-col you"> \
                <div class="ride-pic" ng-switch on="logged_in"> \
                    <div ng-switch-when="false" class="pic user-silhouette"></div> \
                    <div ng-switch-when="true" ng-switch on="!!passenger_picture_url"> \
                        <img class="pic user-picture" border="0" ng-switch-when="true" ng-src="(( passenger_picture_url ))"> \
                        <div class="pic add-picture" ng-switch-when="false" ng-click="update_picture();$event.stopPropagation()"></div> \
                    </div> \
                </div> \
                <div class="name">' + DefaultMessages.you + '</div> \
            </div> \
        '
    }
});
module.directive("ridePicsPassenger", function () {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="ride-pics-col passenger"> \
                <div class="ride-pic" ng-switch on="!!passenger.picture_url"> \
                    <img class="pic user-picture" border="0" ng-switch-when="true" ng-src="(( passenger.picture_url ))"> \
                    <div class="pic user-silhouette" ng-switch-when="false"></div> \
                </div> \
                <div class="name">(( passenger.name ))</div> \
            </div> \
        '
    }
});
module.directive("ridePicsSeat", function () {
    return {
        restrict: 'E',
        replace: true,
        template: '<div class="ride-pics-col">\
                        <div class="ride-pic">\
                            <div class="pic empty-seat"> </div> \
                        </div>\
                    </div>\
        '
    }
});