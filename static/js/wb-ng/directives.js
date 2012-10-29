var module = angular.module('wbDirectives', ['wbMessages']);

// todo: translate. see https://docs.djangoproject.com/en/1.3/topics/i18n/internationalization/#specifying-translation-strings-in-javascript-code

module.directive("offer", function () {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="offer row-fluid"> \
                <div class="offer-passengers span4"> \
                    <div class="type-indicator"></div>\
                    <ride-pics-for-offer></ride-pics-for-offer> \
                </div> \
                <div class="offer-pickup-details span4"> \
                    <strong>Pickup: (( offer.pickup_time | wb_date:"EEE d/M" )) ((  offer.pickup_time | date:"H:mm" ))</strong> \
                    <div>(( offer.seats_left )) Availabe Seats</div> \
                </div> \
                <div class="offer-price-details span4"> \
                    <strong class="price">(( offer.price | currency:"₪" ))</strong> \
                    <span>or less</span> \
                </div> \
            </div>'
    }
});
module.directive("offerAction", function (DefaultMessages) {
    return {
        restrict: 'E',
        compile: function(element, attrs){
            var action_text = attrs.type == "existing" ? DefaultMessages.book_existing_ride_txt : DefaultMessages.book_new_ride_txt;
            var html_text = '<div class="offer-action row-fluid">' +
                                '<div class="offer-comment span8" ng-show="offer.comment">(( offer.comment ))</div>' +
                                '<div class="span4 pull-right"><button class="btn btn-warning btn-block btn-large" ng-click="book_ride()" ng-disabled="loading">' + action_text +' </button></div>' +
                                '<div class="clearfix"></div>' +
                            '</div>';
            element.replaceWith(html_text);
        }
    }
});
module.directive("offerSep", function () {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="offer-sep"> \
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
module.directive("ridePicsYou", function () {
    return {
        restrict: 'E',
        replace: true,
        template: '\
            <div class="ride-pics-col you"> \
                <div class="ride-pic" ng-switch on="logged_in"> \
                    <div ng-switch-when="false" class="pic user-silhouette"></div> \
                    <div ng-switch-when="true" ng-switch on="!!passenger_picture_url"> \
                        <img class="pic user-picture" border="0" ng-switch-when="true" ng-src="(( passenger_picture_url ))"> \
                        <div class="pic add-picture" ng-switch-when="false" ng-click="update_picture()"></div> \
                    </div> \
                </div> \
                <div class="name">את/ה</div> \
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