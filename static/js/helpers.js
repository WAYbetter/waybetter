var BookingHelper = Object.create({
    num_seats: 1,
    hotspot: undefined,
    address: undefined,
    hotspot_type: undefined,
    ride_date: undefined,
    ride_time: undefined,
    messages: {}
});

var MyRidesHelper = Object.create({
    config: {
        rtl: false,
        urls: {
            get_myrides_data: "",
            get_order_status: "",
            cancel_order: ""
        },
        messages: {
            cancel_ride_link: "",
            ride_cancelled: "",
            cancel_text: "",
            report_text: ""
        },
        order_types: {},
        next_rides_table: undefined,
        next_rides_container: undefined,
        previous_rides_table: undefined,
        tip: "#myrides_tooltip",
        tip_content: {
            error: "#error_tip",
            pending: "#ride_pending_tip",
            submitted: "#ride_submitted_tip",
            completed: "#ride_completed_tip",
            report_ride: "#report_ride_tip"
        }
    },

    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);
    },

    getData: function(data, callbacks) {
        var that = this;
        $.ajax({
            url: that.config.urls.get_myrides_data,
            dataType: "json",
            data: data,
            success: function(data) {
                var has_next = (data.next_rides || []).length > 0;
                var has_previous = (data.previous_rides || []).length > 0;
                var $next_table = $(that.config.next_rides_table).eq(0);
                var $previous_table = $(that.config.previous_rides_table).eq(0);

                if ($next_table && has_next) {
                    $.each(data.next_rides, function(i, order) {
                        var row = that._renderRideRow(order, true);
                        $next_table.find("tbody").prepend(row);
                    });
                    $next_table.show();
                }
                else {
                    $next_table.hide();
                }

                if ($previous_table && has_previous) {
                    $.each(data.previous_rides, function(i, order) {
                        var row = that._renderRideRow(order, false);
                        $previous_table.find("tbody").prepend(row);
                    });
                    $previous_table.show();
                }
                else {
                    $previous_table.hide();
                }

                if (callbacks.success) callbacks.success.call(undefined, has_next, has_previous);
            },
            error: (callbacks.error || function() {
            })
        });
    },

    _renderRideRow: function(order, is_next) {
        var that = this;

        var $row = $('<tr data-order_id="' + order.id + '"></tr>');
        switch (order.type) {
            case this.config.order_types['private']:
                $row.append('<td class="private-img"></td>');
                break;
            case this.config.order_types['shared']:
                $row.append('<td class="shared-img"></td>');
                break;
            default:
                $row.append('<td></td>');
        }
        $row.append('<td>' + order.from + '</td>');
        $row.append('<td>' + order.to + '</td>');
        $row.append('<td>' + order.num_seats + '</td>');
        $row.append('<td>' + order.when + '</td>');
        $row.append('<td>' + order.price + '</td>');

        var $info = $('<td class="info' + ((is_next) ? '"' : ' report"') + '></td>');
        if (is_next)
            $info.append('<a class="wb_link">' + this.config.messages.cancel_text + '</a>');
        else
            $info.append('<a class="wb_link">' + this.config.messages.report_text + '</a>');

        $info.tooltip({
            tip: this.config.tip,
            position: (this.config.rtl) ? 'center right' : 'center left',
            relative: true,
            offset: [-30,0],
            events: {
                def: ","
            }
        });
        $info.click(function() {
            (is_next) ? that._showStatusTooltip(this, order.id) : that._showReportTooltip(this, order.id);
        });
        $row.append($info);
        return $row;
    },

    _showStatusTooltip: function(info_el, order_id) {
        var that = this;
        $.ajax({
            url: that.config.urls.get_order_status,
            data: {order_id: order_id},
            dataType: "json",
            success: function(response) {
                var status = response.status;

                if (status == "completed") {
                    var details = response.details;
                    var tip = $(that.config.tip_content.completed);
                    tip.find("#pickup_time_val").text(details.pickup_time);
                    tip.find("#taxi_number_val").text(details.taxi_number);
                    tip.find("#station_name_val").text(details.station_name + " " + details.station_phone);
                }
                if (status == "pending") {
                    var $old_link = $(that.config.tip_content.pending).find("#cancel_ride_link");
                    var $new_link = $('<div id="cancel_ride_link" class="wb_link">' + that.config.messages.cancel_ride_link + '</div>').click(function () {
                        that._cancelOrder(info_el, order_id);
                    });
                    $old_link.replaceWith($new_link);
                }

                that._showTooltip(info_el, status);
            },
            error: function() {
                that._showTooltip(info_el, "error");
            }
        });
    },

    _showReportTooltip: function(info_el, order_id) {
        $(this.config.tip_content.report_ride).find("#report_ride_link").attr("href", "mailto:" + $("#report_ride_link").text() + "?subject=Report Ride " + order_id);
        this._showTooltip(info_el, "report_ride");
    },

    _showTooltip: function(info_el, content) {
        var that = this;
        this._removeCancelledOrders();

        $.each(this.config.tip_content, function(status, content) {
            $(content).hide();
        });

        var api = $(info_el).data("tooltip");
        if (api) {
            var tip = api.getTip();
            if (! tip) { // initialize tip
                api.show();
                tip = api.getTip();
            }

            tip.find(".close").unbind("click").click(function() {
                that._removeCancelledOrders();
                api.hide();
            });

            api.hide();
            api.show();
        }

        $(this.config.tip_content[content]).show();
    },

    _cancelOrder: function(info_el, order_id) {
        var that = this;
        var $tip = $(that.config.tip_content.pending);
        var $loader = $tip.find(".tooltip_loader");
        var $link = $tip.find("#cancel_ride_link");
        $.ajax({
            url: that.config.urls.cancel_order,
            type: "POST",
            data: {order_id: order_id},
            dataType: "json",
            beforeSend: function() {
                $loader.show();
                $link.addClass("disabled");
            },
            complete: function() {
                $loader.hide();
                $link.removeClass("disabled");
            },
            success: function(response) {
                if (response.status == 'cancelled') {
                    $link.removeClass("wb_link").text(that.config.messages.ride_cancelled);
                    $(info_el).parent("tr").addClass("cancelled");
                } else {
                    that._showTooltip(info_el, "error");
                }
            },
            error: function() {
                that._showTooltip(info_el, "error");
            }
        });
    },

    _removeCancelledOrders: function(){
        var that = this;
        var cancelled = $(this.config.next_rides_table).find("tr.cancelled");

        $.each(cancelled, function () {
            $(this).fadeOut("fast", function () {
                $(this).remove();
                var num_rides = $(that.config.next_rides_table).find("tr[data-order_id]").length;
                if (num_rides === 0) { // this is the only ride
                    $(that.config.next_rides_container).fadeOut("fast");
                }
            });

        });
    }
});

var HotspotHelper = Object.create({
    config: {
        selectors: {
            hotspotpicker: undefined,
            datepicker: undefined,
            timepicker: undefined,
            hs_description: undefined
        },
        urls: {
            get_hotspot_data: "",
            get_hotspot_dates: "",
            get_hotspot_offers: ""
        },
        labels: {
            choose_date: "",
            updating: ""
        },
        hotspot_markers: {
            generic: "/static/images/hotspot_red_marker.png",
            pickup: "/static/images/wb_site/map_marker_A.png",
            dropoff: "/static/images/wb_site/map_marker_B.png"
        }
    },
    cache: {
        dates: [],
        months: []
    },

    hotspots: [],
    MapHelper: undefined,
    ride_duration: undefined,

    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);
        this.MapHelper = config.MapHelper || CMHelper;
    },

    clearCache: function() {
        this.cache.dates = [];
        this.cache.months = [];
    },

    getHotspotByID: function(hotspot_id){
        var hotspot = undefined;
        $.each(this.hotspots, function(i, hs) {
            if (hs.id == hotspot_id) {
                hotspot = hs;
                return false;
            }
        });
        return hotspot;
    },

    getHotspotData: function(options) {
        var that = this;
        $.ajax({
            url: that.config.urls.get_hotspot_data,
            data: options.data,
            dataType: "json",
            beforeSend: options.beforeSend,
            success: options.success,
            error: options.error
        });
    },

    getDates: function(options) {
        var that = this;
        $.ajax({
            url: that.config.urls.get_hotspot_dates,
            dataType: "json",
            data: options.data,
            success: options.success,
            error: options.error
        });
    },

    getIntervals: function(options) {
        var that = this;
        var $hotspotpicker = $(this.config.selectors.hotspotpicker);
        var $datepicker = $(this.config.selectors.datepicker);

        $.ajax({
            url: that.config.urls.get_hotspot_offers,
            dataType: "json",
            data: $.extend(true, {'day': $datepicker.val(), 'hotspot_id': $hotspotpicker.val()}, options.data),
            beforeSend: function() {
                that.ride_duration = undefined;
                if (options.beforeSend) {
                    options.beforeSend();
                }
            },
            success: function(response) {
                if (response.ride_duration) {
                    that.ride_duration = response.ride_duration;
                }
                options.success(response);

            },
            error: options.error,
            complete: options.complete || function() {
            }
        });
    },

    refreshHotspotMarker: function(marker_type, zoom) {
        var that = this;
        if (this.MapHelper.mapready) {
            this._refreshHotspotMarker(marker_type);
        }
        else {
            // wait for it..
            $(window).one("mapready", function() {
                that._refreshHotspotMarker(marker_type);
            });
        }
    },

    _refreshHotspotMarker: function(marker_type, zoom) {
        var $selected = $(this.config.selectors.hotspotpicker).find(":selected").eq(0);
        var lat = $selected.data("lat");
        var lon = $selected.data("lon");
        if (lat && lon && this.MapHelper) {
            var marker_name = "hotspot";
            var img = this.config.hotspot_markers[marker_type] || this.config.hotspot_markers.generic;
            this.MapHelper.addMarker(lat, lon, {icon_image: img, title: $selected.text(), marker_name: marker_name});
            this.MapHelper.zoomMarker(marker_name);
        }
    },

    makeHotSpotSelector: function(options) {
        options = $.extend(true, {
            onSelectDate: function(dateText, inst) {
            },
            onSelectTime: function() {
            }
        }, options);
        var that = this;
        var $hotspotpicker = $(this.config.selectors.hotspotpicker);
        var $datepicker = $(this.config.selectors.datepicker);
        var $timepicker = $(this.config.selectors.timepicker);
        var $hs_description = $(this.config.selectors.hs_description);


        this.getHotspotData({
            beforeSend: function() {
                $hotspotpicker.empty().disable().append("<option>" + that.config.labels.updating + "</option>");
            },
            success: function(response) {
                $hotspotpicker.empty().enable();
                $.each(response.data, function(i, hotspot) {
                    that.hotspots.push(hotspot);
                    var data = {id: hotspot.id, lon: hotspot.lon, lat: hotspot.lat, name: hotspot.name,
                        description: hotspot.description, next_datetime: new Date(hotspot.next_datetime)};
                    var text = (hotspot.description) ? hotspot.name + " (" + hotspot.description + ")" : hotspot.name;
                    $("<option>" + text + "</option>").attr("value", hotspot.id).data(data).appendTo($hotspotpicker);
                });

                $hotspotpicker.change(function() {
                    var $selected = $hotspotpicker.find(":selected").eq(0);
                    if ($selected) {
                        $hs_description.text("").text($selected.data("description"));
                        var first_interval = $selected.data("next_datetime") || new Date();

                        $datepicker.datepicker("destroy").datepicker({
                            dateFormat: 'dd/mm/yy',
                            minDate: new Date(),
                            isRTL: true,
                            beforeShowDay: function(date) {
                                return ($.inArray(date.toDateString(), that.cache.dates) !== -1) ? [true, "", ""] : [false, "", ""];
                            },
                            onSelect: options.onSelectDate,
                            onChangeMonthYear: that._onChangeMonthYear
                        }).datepicker("setDate", getFullDate(first_interval));

                        // get dates
                        that.clearCache();
                        that._getDatesForMonthYear(first_interval.getFullYear(), first_interval.getMonth()+1, $datepicker);
                    }
                });

                $hotspotpicker.change();

                $timepicker.empty().disable().change(function() {
                    options.onSelectTime();
                });

                if (options.successCallback){
                    options.successCallback();
                }
            },
            error:function() {
                flashError("Error getting hotspot data");
            }
        });
    },

    refreshHotspotSelector: function(options) {
        options = $.extend(true, {}, options);
        var that = this;
        var $hotspotpicker = $(this.config.selectors.hotspotpicker);
        var $datepicker = $(this.config.selectors.datepicker);
        var $timepicker = $(this.config.selectors.timepicker);

        if (options.refresh_intervals) {
            var times = [];
            this.getIntervals({
                data: options.get_intervals_data,
                beforeSend: function() {
                    $timepicker.empty().disable().append("<option>" + that.config.labels.updating + "</option>");
                    if (!$datepicker.val()) {
                        $datepicker.datepicker("setDate", getFullDate($("#id_hotspot_select option:selected").data("next_datetime")));
                    }
                    if (options.beforeSend) {
                        options.beforeSend();
                    }
                },
                success: function(response) {
                    if (response.times && response.times.length) {
                        times = response.times;
                        $timepicker.empty();
                        $.each(response.times, function(i, t) {
                            $timepicker.append("<option>" + t + "</option>");
                        });
                        $timepicker.enable().change();
                    }
                },
                error: function() {
                    if (options.error) {
                        options.error();
                    }
                },
                complete: function() {
                    if (options.complete) {
                        options.complete();
                    }
                    if (times.length) {
                        if (options.onGotTimes)
                            options.onGotTimes(times);
                    }
                    else {
                        if (options.onNoTimes)
                            options.onNoTimes();
                    }
                }
            });

        }
    },

    _onChangeMonthYear: function(year, month, inst) {
        if ($.inArray(month, HotspotHelper.cache.months) < 0) {
            // get dates for this month
            HotspotHelper._getDatesForMonthYear(year, month, inst.input);
        }
    },

    _getDatesForMonthYear: function(year, month, $datepicker) {
        var that = this;
        that.getDates({
            data: {'month': month, 'year': year, 'hotspot_id': $(that.config.selectors.hotspotpicker).val()},
            success: function(response) {
                var new_dates = $.map(response.dates, function(date, i) {
                    return (new Date(date)).toDateString();
                });
                that.cache.dates = that.cache.dates.concat(new_dates);
                that.cache.months[that.cache.months.length] = month;
                $datepicker.datepicker("refresh");
            },
            error: function() {
                flashError("Error loading hotspot dates data");
            }
        });
    }
});

var AddressHelper = Object.create({
    config: {
        urls:{
            structured_resolve_url: ""
        },
        messages:{
            choose_from_list: ""
        }
    },

    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);
    },

    makeStructuredAddressInput: function(city_selector, street_input, hn_input, loader, callbacks) {
        callbacks = $.extend(true, {}, callbacks);
        var that = this,
                $street_input = $(street_input),
                $hn_input = $(hn_input),
                $loader = $(loader);

        function _beforeSend() {
            $loader.show();
        }

        function _complete() {
            $loader.hide();
        }

        $street_input.data("resolved", false);
        $street_input.autocomplete({
            autoFocus: true,
            minLength: 2,
            source: function(request, response) {
                $.ajax({
                    url: that.config.urls.structured_resolve_url,
                    data: {"city_id": $(city_selector).val(), "street": $street_input.val(), "house_number": $hn_input.val()},
                    dataType: "json",
                    beforeSend: _beforeSend,
                    complete: _complete,
                    success: function(data) {
                        response($.map(data.geocoding_results, function(item) {
                            return {
                                label: item.street_address
                            }
                        }));
                    },
                    error: function() {
                        response([]);
                    }
                });
            },
            select: function(event, ui) {
                $(this).data("resolved", true);
                $(this).blur().autocomplete("disable");
                $hn_input.focus();
                if (callbacks.success)
                    callbacks.success();
                $(this).trigger("change");
            }

        });

        $street_input.blur(function() {
            $loader.hide();
            $(this).autocomplete("disable");
        }).focus(function() {
            $(this).autocomplete("enable");
            $(this).autocomplete("search");
            $(this).data("old_val", $(this).val());
        }).keyup(function(e) {
            if ($(this).data("old_val") !== $(this).val()) {
                $(this).data("resolved", false);
            }
        });
    },

    resolveStructured: function(options) {
        var that = this,
                $city_selector = $(options.city_selector),
                $street_input = $(options.street_input),
                $hn_input = $(options.hn_input),
                callbacks = options.callbacks;

        function _beforeSend() {
            $.each([$city_selector, $street_input, $hn_input], function() {
                $(this).disable();
            });
            if (callbacks && callbacks.beforeSend) {
                callbacks.beforeSend();
            }
        }

        function _complete() {
            $.each([$city_selector, $street_input, $hn_input], function() {
                $(this).enable();
            });
            if (callbacks && callbacks.complete) callbacks.complete();
        }

        function _resolved(result) {
            if (callbacks && callbacks.resolved) callbacks.resolved(result);
        }

        function _unresolved(errors) {
            if (callbacks && callbacks.unresolved) callbacks.unresolved(errors);
        }

        function _error() {
            if (callbacks && callbacks.error) callbacks.error();
        }

        var query = {"city_id": $city_selector.val(), "street": $street_input.val(), "house_number": $hn_input.val()};
        $.ajax({
            url: that.config.urls.structured_resolve_url,
            data: query,
            dataType: "json",
            beforeSend: _beforeSend,
            complete: _complete,
            success: function(data) {
                if (data.errors) {
                    _unresolved(data.errors);
                }
                else {
                    var match = undefined;
                    var suggestions = [];
                    $.each(data.geocoding_results, function(i, result) {
                        if (result.lat && result.lon && result.street_address && result.house_number) { // this is a valid result
                            suggestions.push(result);
                            if (result.street_address == query.street && result.house_number == query.house_number) {
                                match = result;
                                return false; // break;
                            }
                        }
                    });
                    if (options.return_multiple) {
                        if (suggestions.length)
                            _resolved(suggestions);
                    } else {
                        if (match) {
                            $street_input.autocomplete("close");
                            _resolved(match);
                        }
                        else
                            _unresolved({street: that.config.messages.choose_from_list});
                    }

                }
            },
            error: _error
        });
    }

});

var GoogleGeocodingHelper = Object.create({
    _geocoder: undefined,
    getGeocoder: function() {
        if (! this._geocoder) {
            this._geocoder =  new google.maps.Geocoder();
        }
        return this._geocoder;
    },
    geocode: function(address, callback){
        this.getGeocoder().geocode({"address":address}, function (results, status) {
            callback(results, status);
        });
    },
    reverseGeocode:function (lat, lon, callback) {
        var latlng = new google.maps.LatLng(lat, lon);
        this.getGeocoder().geocode({'latLng':latlng}, function (results, status) {
            callback(results, status);
        });
    },
    newPlacesAutocomplete: function (options) {
        options = $.extend(true, {
            id_textinput: "",
            beforePlaceChange: function(){},
            onValidAddress: function(address){},
            onMissingStreetNumber: function(){},
            onNoValidPlace: function(){}
        }, options);

        var autocomplete = new google.maps.places.Autocomplete(document.getElementById(options.id_textinput),
            {
                bounds: options.bounds || undefined,
                types: options.types || []
            });

        if (options.map){
            autocomplete.bindTo('bounds', options.map);
        }

        var that = this;
        google.maps.event.addListener(autocomplete, 'place_changed', function () {
            var place = this.getPlace();
            options.beforePlaceChange();
            that._onNewPlace.call(that, place, options);
        });

        return autocomplete;
    },
    showAutocomplete: function(){
        $(".pac-container").css("visibility", "visible");
    },
    hideAutocomplete: function(){
        $(".pac-container").css("visibility", "hidden");
    },
    _onNewPlace:function (place, options) {
        var result = this._checkValidPickupAddress(place, options.id_textinput);

        if (result.valid) {
            options.onValidAddress(result.address);
        }
        else if (result.is_route) {
            options.onMissingStreetNumber();
        }
        else if (place.geometry && place.geometry.location) {
            // try to get a valid point by reverse geocoding
            this.reverseGeocode(place.geometry.location.lat(), place.geometry.location.lng(), function (results, status) {
                var rev_result;
                if (status == google.maps.GeocoderStatus.OK && results.length) {
                    log("reverse geocode results:", results, "for place:", place);
                    rev_result = GoogleGeocodingHelper._checkValidPickupAddress(results[0], options.id_textinput);
                } else {
                    log("Geocoder failed due to: " + status);
                }

                if (rev_result) {
                    $("#" + options.id_textinput).val(results[0].formatted_address); // let the user see what we are validating
                    if (rev_result.valid)
                        options.onValidAddress(rev_result.address);
                    else if (rev_result.is_route)
                        options.onMissingStreetNumber();
                }
                else {
                    options.onNoValidPlace();
                }
            });
        }
        else {
            options.onNoValidPlace();
        }
    },
    _checkValidPickupAddress: function(place, id_textinput){
        var is_route, is_establishment, is_of_valid_type;
        var valid_types = ["street_address", "train_station", "transit_station"];

        var result = {
            valid: false,
            is_route: false,
            address: undefined
        };

        if (place.types) {
            $.each(place.types, function (i, type) {
                if ($.inArray(type, valid_types) > -1)
                    is_of_valid_type = type;
                if (type == "route")
                    is_route = true;
                if (type == "establishment")
                    is_establishment = true;
            });
        }

        if (is_of_valid_type) {
            result.valid = true;
            log("valid type: " + is_of_valid_type);
        }
        else if (is_route){
            // street with no house number, ask the user to enter it
            result.valid = false;
            result.is_route = true;
            log("route: ask for house number");
        }
        else if (is_establishment) {
            if (place.address_components) {
                // maybe address components contain some useful information
                var street_number_component = undefined;
                var route_component = undefined;
                $.each(place.address_components, function (i, component) {
                    if (component.types) {
                        if ($.inArray('route', component.types) > -1) {
                            route_component = component;
                        }
                        if ($.inArray('street_number', component.types) > -1) {
                            street_number_component = component;
                        }
                    }
                });
                if (route_component && street_number_component) {
                    var user_input = $("#" + id_textinput).val();

                    if (user_input.startsWith(route_component.short_name) && user_input.search(street_number_component.short_name) < 0) {
                        // the user entered a street with no number which resolves as establishment
                        result.is_route = true;
                        log("establishment: probably a route");
                    }
                    else{
                        result.valid = true;
                        log("establishment: street address found");
                    }
                }
                else{
                    log("establishment: no address found");
                }
            }
        }

        result.address = this._addressFromPlace(place);
        return result;
    },
    _addressFromPlace: function(place){
        place = this._normalizePlace(place);

        // address fields
        var street_address, house_number, city, name, lat, lon;

        var address_components = place.address_components || [];
        $.each(address_components, function (i, component) {
            var type = component.types[0];
            if (type == 'locality')
                city = component.long_name;
            else if (type == "route")
                street_address = component.long_name;
            else if (type == 'street_number')
                house_number = component.short_name; // normalized field
        });

        if (place.geometry && place.geometry.location){
            lat = place.geometry.location.lat();
            lon = place.geometry.location.lng();
        }

        if (street_address && house_number && city){
            name = street_address + " " + house_number + ", " + city;
        }
        else if (place.formatted_address){
            name = place.formatted_address;
        }

        return {
            city:city,
            street_address:street_address,
            house_number:house_number,
            name:name,
            lat:lat,
            lon:lon
        };
    },
    _normalizePlace: function(place){
        try {
            // fix interpolated street number component
            if (place.geometry.location_type == google.maps.GeocoderLocationType.RANGE_INTERPOLATED) {
                $.each(place.address_components, function (i, component) {
                        if (component.types && $.inArray('street_number', component.types) > -1) {
                            // get the lower street number of the range
                            var range = component.long_name.split("-");
                            if (range.length == 2){
                                var low = range[0];
                                var high = range[1];
                                component.short_name = parseInt((high-low)/2); // take the middle house number
                            }
                            place.formatted_address = place.formatted_address.replace(component.long_name, component.short_name);
                        }
                    }
                );
            }
        }
        catch (e) {
            log(e);
        }

        return place;
    }
});

var GoogleMapHelper = Object.create({
    config:{
        map_element:undefined,
        map:undefined,
        map_options:{
            zoom:14
        },
        traffic: true
    },
    mapready:false,
    markers: {},

    init: function(config){
        var that = this;
        this.config = $.extend(true, {}, this.config, config);
        this.map = new google.maps.Map(document.getElementById(this.config.map_element), this.config.map_options);

        google.maps.event.addListener(this.map, 'tilesloaded', function () {
            that.mapready = true;
            $(window).trigger("mapready");
        });

        if (this.config.traffic){
            var trafficLayer = new google.maps.TrafficLayer();
            trafficLayer.setMap(this.map)
        }
    },
    zoomMarker: function(marker_name){
        var marker = this.markers[marker_name];
        if (marker){
            this.map.setCenter(marker.getPosition());
            this.map.setZoom(17);
        }
    },
    fitMarkers: function(){
        var bounds = new google.maps.LatLngBounds();

        var num_markers = 0;
        $.each(this.markers, function (i, marker) {
            num_markers++;
            bounds = bounds.extend(marker.getPosition());
        });

        if (num_markers > 1) {
            this.map.fitBounds(bounds);
        }
        else {
            this.map.setCenter(latLng);
            this.map.setZoom(15);
        }

    },
    addMarker:function (lat, lon, options) {
        var that = this;
        options = $.extend(true, {}, options);
        // remove old marker with the same name or position
        var marker_name = options.marker_name || lat + "_" + lon;
        marker_name = marker_name.split(".").join("_"); // replace . with _
        var old_marker = this.markers[marker_name];
        if (old_marker){
            old_marker.setMap(null);
        }

        // add the new marker
        var latLng = new google.maps.LatLng(lat, lon);
        var markerOptions = {
            map: this.map,
            position:latLng,
            title: "",
            clickable: false
//            animation:google.maps.Animation.DROP
        };
        markerOptions = $.extend(true, markerOptions, options);
        if (options.icon_image){
            markerOptions.icon = new google.maps.MarkerImage(options.icon_image);
        }

        this.markers[marker_name] = new google.maps.Marker(markerOptions);
        return this.markers[marker_name];
    },
    addAMarker:function (lat, lon, options) {
        options = $.extend(true, {}, {icon_image: "/static/images/wb_site/map_marker_A.png", marker_name:"A"}, options);
        return this.addMarker(lat, lon, options);
    },
    addBMarker:function (lat, lon, options) {
        options = $.extend(true, {}, {icon_image:"/static/images/wb_site/map_marker_B.png", marker_name:"B"}, options);
        return this.addMarker(lat, lon, options);
    },
    removeMarker:function (names) {
        var that = this;
        if (names == "all") {
            $.each(this.markers, function (i, marker) {
                marker.setMap(null);
            });
            that.markers = {};
        }
        else {
            $.each(names.split(","), function (i, name) {
                name = name.trim();
                var marker = that.markers[name];
                if (marker) {
                    marker.setMap(null);
                    delete that.markers[name];
                }
            })
        }
    },
    showInfo: function(content, anchor) {
        var info = new google.maps.InfoWindow({
            content: content
        });

        info.open(this.map);
    }
});

var CMHelper = Object.create({
    config: {
        api_key: '',
        map_element: 'cm-map',
        styleId: 45836,
        center_lat: 32.09279909028302,
        center_lon: 34.781051985221,
        icon_image: "/static/images/wb_site/map_marker_A_centerfix.png",
        icon_size_x: 61,
        icon_size_y: 154,
        controls: true
    },
    map: undefined,
    markers: {},
    icon: undefined,
    mapready: false,

    init: function(config) {
        var that = this;
        this.config = $.extend(true, {}, this.config, config);

        var cloudmade = new CM.Tiles.CloudMade.Web({
            key: this.config.api_key,
            styleId: this.config.styleId
//            copyright: ""
        });

        this.map = new CM.Map(this.config.map_element, cloudmade);
        this.map.setCenter(new CM.LatLng(this.config.center_lat, this.config.center_lon), 15);
        this.map.disableScrollWheelZoom();

        if (this.config.controls){
            var myControl = new CM.SmallMapControl();
            this.map.addControl(myControl);
        }

        this.icon = new CM.Icon();
        this.icon.image = this.config.icon_image;
        this.icon.iconSize = new CM.Size(this.config.icon_size_x, this.config.icon_size_y);

        // TODO_WB: why load event is not fired?
        //CM.Event.addListener(this.map, 'load', function() {alert("foo")});
        $(window).oneTime(1e3, function mapLoaded() {
            if (that.map.isLoaded()) {
                that.mapready = true;
                $(window).trigger("mapready");
            }
            else {
                mapLoaded();
            }
        });

        window.onresize = function() {
            that.map.checkResize();
        };
    },

    addMarker: function(lat, lon, options) {
        options = $.extend(true, {}, options);
        var title = options.title || "";
        var zoom = options.zoom || 14;
        var icon_image = options.icon_image || undefined;
        var icon = options.icon || new CM.Icon(this.icon, icon_image);
        var marker_name = options.marker_name || undefined;

        var myMarkerLatLng = new CM.LatLng(lat, lon);
        var myMarker = new CM.Marker(myMarkerLatLng, {
            title: title,
            icon: icon,
            clickable: false
        });
        this.map.addOverlay(myMarker);

        if (marker_name) {
            var old_marker = this.markers[marker_name];
            if (old_marker) {
                this.map.removeOverlay(old_marker);
            }
            this.markers[marker_name] = myMarker;
        }

        var bounds = [];
        $.each(this.markers, function(i, marker) {
            bounds.push(marker.getLatLng());
        });

        if (bounds.length > 1) {
            var _bounds = new CM.LatLngBounds(bounds);
            this.map.zoomToBounds(_bounds);
            this.map.setZoom(this.map.getZoom() - 1);
        }
        else {
            this.map.setCenter(myMarkerLatLng, 17);
        }
    },

    addAMarker: function(lat, lon, options) {
        options = $.extend(true, {}, options, {icon_image: "/static/images/wb_site/map_marker_A_centerfix.png", marker_name: "A"});
        this.addMarker(lat, lon, options);
    },
    addBMarker: function(lat, lon, options) {
        options = $.extend(true, {}, options, {icon_image: "/static/images/wb_site/map_marker_B_centerfix.png", marker_name: "B"});
        this.addMarker(lat, lon, options);
    },
    removeMarker: function(names) {
        var that = this;
        if (names == "all") {
            $.each(this.markers, function(i, marker) {
                that.map.removeOverlay(marker);
            });
            that.markers = {};
        }
        else {
            $.each(names.split(","), function(i, name){
                name = name.trim();
                var marker = that.markers[name];
                if (marker) {
                    that.map.removeOverlay(marker);
                    delete that.markers[name];
                }
            })
        }
    }
});

var TelmapHelper = Object.create({
    config:     {
        telmap_user:                "",
        telmap_password:            "",
        telmap_languages:           ""
    },

    mapready:                       false,
    map:                            {},
    map_markers:                    {},
    map_markers_popups:             {},
    map_was_reset:                  false,
    telmap_prefs:                   {},

    init:                       function(config) {
        var that = this;
        this.config = $.extend(true, {}, this.config, config);
        this.telmap_prefs = {
            mapTypeId:telmap.maps.MapTypeId.ROADMAP,
            suit:telmap.maps.SuitType.MEDIUM_4,
            navigationControlOptions:{style:telmap.maps.NavigationControlStyle.ANDROID},
            zoom:15,
            center:new telmap.maps.LatLng(32.09279909028302, 34.781051985221),
            login:{
                contextUrl: 'api.telmap.com/telmapnav',
                userName:   this.config.telmap_user,
                password:   this.config.telmap_password,
                languages:  [this.config.telmap_languages, this.config.telmap_languages],
                appName:    'wayBetter',
                callback:   function () {
                    that.resetMap.call(that);
                }
            }

        };

        this.map = new telmap.maps.Map(document.getElementById("map"), this.telmap_prefs);
        window.onresize = function() {
            telmap.maps.event.trigger(this.map, "resize");
        };
        telmap.maps.event.addListener(this.map, 'tilesloaded', function() {
            that.mapready = true;
            $(window).trigger("mapready");
        });
        return this;
    },
    resetMap:                 function (e, a) {
        var that = this;
        if (! this.map_was_reset) {
            this.map_was_reset = true;
            this.map.logout(function(e, a) {
                that.map.login(that.telmap_prefs.login);
            });
        }
    },
    addMarker: function(lat, lon) {
        var hotsport_marker_image = '/static/images/hotspot_red_marker.png';
        var hotsport_marker_offset = {x:32, y:63};

        var icon_image = new telmap.maps.MarkerImage(hotsport_marker_image, undefined, undefined, hotsport_marker_offset);
        var point = new telmap.maps.Marker({
            map:        this.map,
            position:   new telmap.maps.LatLng(lat, lon),
            icon:       icon_image,
            title:      "Hotspot"
        });

        this.removePoint("hotspot");
        this.map_markers["hotspot"] = point;
        this.renderMapMarkers();
    },
    removePoint:                function(address_type) {
        if (this.map_markers[address_type]) {
            this.map_markers[address_type].setMap(); // remove old marker from map
        }
    },
    renderMapMarkers:           function () {
        var that = this,
                map = this.map,
                markers = 0,
                bounds = new telmap.maps.LatLngBounds();

        $.each(this.map_markers, function (i, point) {
            markers++;
            bounds.extend(point.getPosition());
            var info = new telmap.maps.InfoWindow({
                content: "<div style='font-family:Arial,sans-serif;font-size:0.8em;'>" + point.location_name + "<div>",
                disableAutoPan: true
            });

            if (that.map_markers_popups[i]) {
                that.map_markers_popups[i].close();
            }
            that.map_markers_popups[i] = info;

        });
        if (markers > 1) {
            // make room for estimation box
            var delta = (bounds.ne.y - bounds.sw.y) * 0.5;
            var newPoint = new telmap.maps.LatLng(bounds.ne.y + delta, bounds.ne.x);
            bounds.extend(newPoint);

            map.fitBounds(bounds);
            map.panToBounds(bounds);

        } else if (bounds.valid) {
            map.panTo(bounds.getCenter());
        }
    }
});

var SocialHelper = Object.create({
    config:{
        messages:{
            email:{
                subject: "",
                body: ""
            },
            facebook:{
                share_msg: ""
            },
            twitter:{
                share_msg: ""
            }
        }
    },
    init:function (config) {
        this.config = $.extend(true, {}, this.config, config);
    },
    getEmailShareLink:function (options) {
        options = $.extend(true, {
            subject: this.config.messages.email.subject,
            body: this.config.messages.email.body}, options);
        return "mailto:?subject=" + options.subject + "&body=" + options.body;
    },
    getTwitterShareLink:function (msg) {
        msg = msg || this.config.messages.twitter.share_msg;
        return "http://twitter.com/share?text=" + msg + "&url=http://www.WAYbetter.com";
    },
    getFacebookShareLink:function (mobile) {
        var url = "http://" + ((mobile) ? "m" : "www") + ".facebook.com/dialog/feed?" +
            "&app_id=280509678631025" +
            "&link=http://www.WAYbetter.com" +
            "&picture=http://www.waybetter.com/static/images/wb_site/wb_beta_logo.png" +
            "&name=" + "WAYbetter" +
            //                    "&caption=" +
            "&description=" + encodeURIComponent(this.config.messages.facebook.share_msg) +
            "&redirect_uri=http://www.waybetter.com";
        if (mobile) {
            url += "&display=touch"
        }

        return url;
    },
    getFacebookLikeLink:function (mobile) {
        return "http://" + ((mobile) ? "m" : "www") + ".facebook.com/pages/WAYbetter/131114610286539";
    }
});

var MobileHelper = Object.create({
    config: {
        urls:{
            resolve_coordinates     : "",
            get_hotspot_dates       : "",
            get_myrides_data        : "",
            cancel_order            : "",
            get_sharing_cities      : ""
        },
        callbacks:{
            noGeolocation: function() { },
            locationSuccess: function() { },
            locationError: function(watch_id) {
                navigator.geolocation.clearWatch(watch_id); // remove watch
            }
        }
    },

    MapHelper: undefined,

    // CONSTANTS
    // ---------
    ACCURACY_THRESHOLD: 250, // meters,

    // VARIABLES
    // ---------
    last_position: undefined,
    num_seats: 1,
    address: undefined,
    hotspot: undefined,
    hotspot_type: "dropoff",
    ride_date: undefined,
    ride_time: undefined,
    sharing_cities: [],

    // METHODS
    // -------
    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);
    },

    getSharingCities: function(options) {
        options = $.extend(true, {}, options);
        var that = this;
        $.ajax({
            url: that.config.urls.get_sharing_cities,
            success: function(data) {
                that.sharing_cities = data;
                if (options.success){
                    options.success();
                }
            }
        })
    },

    getCurrentLocation: function(options) {
        var that = this;
        options = $.extend({}, {
                    locationSuccess: that.config.callbacks.locationSuccess,
                    locationError: that.config.callbacks.locationError
                }, options);

        var config = {
            timeout: 5000, // 5 second
            enableHighAccuracy: true,
            maximumAge: 0 // always get new location
        };

        if (navigator.geolocation) {

            var watch_id = navigator.geolocation.watchPosition(function(p) {
                        log("new position: " + p.coords.longitude + ", " + p.coords.latitude + " (" + p.coords.accuracy + ")");
                        that.last_position = p;
                        if (p.coords.accuracy < that.ACCURACY_THRESHOLD) {
                            navigator.geolocation.clearWatch(watch_id); // we have an accurate enough location

                            options.locationSuccess(p);
                        }
                    }, function(e) {
                        log("location error: " + e.message);
                        options.locationError(watch_id);
                    }, config);
        } else {
            this.config.callbacks.noGeolocation();
        }
    },

    resolveLonLat: function(lon, lat, options) {
        var that = this;
        options = $.extend({}, {
                    onNewAddress: function(address) {
                    },
                    noAddressFound: function() {
                        log("resolve to address failed");
                    }
                }, options);
        $.ajax({
            url:that.config.urls.resolve_coordinates,
            type:"GET",
            data:{ lat:lat, lon:lon },
            dataType:"json",
            success:function(address) {
                if (address && address.street_address && address.house_number) {
                    options.onNewAddress(address);
                } else {
                    options.noAddressFound();
                }
            },
            complete:function() {
            }
        });
    },
    distance    : function(lat1, lon1, lat2, lon2) {
        var p1 = new LatLon(lat1, lon1);
        var p2 = new LatLon(lat2, lon2);

        return p1.distanceTo(p2);
    },
    updateMyRidesBubble:    function(button_selector) {
        var that = this;
        var $btn = $(button_selector);
        $.ajax({
            url: that.config.urls.get_myrides_data,
            dataType: "json",
            data: {get_next_rides: true},
            success: function(data) {
                if (data && data.next_rides) {
                    var num = data.next_rides.length;
                    var $bubble = undefined;
                    if (num > 0) {
                        if ($btn.find(".bubble").length === 0) {
                            $bubble = $("<span class='bubble'></span>");
                            $btn.append($bubble);
                        } else {
                            $bubble = $btn.find(".bubble");
                        }
                        $bubble.text(num).show();
                    } else {
                        $btn.find(".bubble").hide();
                    }
                } else {
                    $btn.find(".bubble").hide();
                }
            },
            error: function() {
                $btn.find(".bubble").hide();
            }
        })

    },
    getMyRidesData: function(options, list_selector, ride_page_selector) {
        var that = this;
        var $list = $(list_selector);

        $.ajax({
            url: that.config.urls.get_myrides_data,
            dataType: "json",
            data: options,
            success: function(data) {
                //data.previous_rides || []);
                $list.empty();
                var ride_data = [];
                if (data.previous_rides) {
                    ride_data = data.previous_rides;
                } else if (data.next_rides) {
                    ride_data = data.next_rides;
                }

                if (ride_data.length) {
                    $.each(ride_data, function(i, ride) {
                        var $li_header = $('<li data-role="list-divider"></li>').text(that.config.labels.pickupat + ": " + ride.when).attr("id", "ride_header_" + ride.id);
                        var $li_a = $('<a href="#"></a>');
                        $li_a.append("<p>" + that.config.labels.pickup + ": " + ride.from + "</p>");
                        $li_a.append("<p>" + that.config.labels.dropoff + ": "+ ride.to + "</p>");
                        $li_a.append("<p>" + that.config.labels.price + ": "+ ride.price + " &#8362;</p>");
                        $li_a.click(function() {
                            that.showRideStatus(ride, ride_page_selector);
                        });

                        var $li_ride = $('<li data-icon="arrow-l"></li>').attr("id", "ride_li_" + ride.id).append($li_a);

                        $list.append($li_header);
                        $list.append($li_ride);
                    });
                    $list.listview("refresh");
                }
            },
            complete: function() {
                try {
                    $list.listview("refresh");
                } catch(e) {
                    $list.listview();
                }
            }
        })
    },
    showRideStatus  : function(ride_data) {
        var that = this;

        var $ride_page = $(that.config.selectors.ride_details_page);
        var $ride_details = $(that.config.selectors.ride_details);
        var $details_btn = $(that.config.selectors.ride_details_btn);

        $ride_details.find(".pickup .text").text(ride_data['from']);
        $ride_details.find(".dropoff .text").text(ride_data['to']);
        $ride_details.find(".when .text").text(ride_data['when']);
        $ride_details.find(".price .text").text(ride_data['price'] + " ₪");

        $.ajax({
            url: that.config.urls.get_order_status,
            data: {order_id: ride_data.id},
            dataType: "json",
            success: function(response) {
                var status = response.status;
                var details = response.details;

                if (status == "pending") {
                    $details_btn.set_button_text(that.config.labels.cancel_ride);
                    $details_btn.attr("href", "#").unbind("click").click(function () {
                        that.cancelOrder(ride_data.id);
                        return false;
                    });
                    $ride_page.find(".ride_details_comment").text(that.config.labels.sms_sent);
                } else {
                    $details_btn.attr("href", "mailto:support@waybetter.com?subject=Regarding order " + ride_data.id);
                    $details_btn.set_button_text(that.config.labels.report_ride);
                    $details_btn.unbind("click"); // default behavior is report via mailto: link

                    var comment = "";
                    if (details && details.pickup_time) {
                        comment += "<p>" + that.config.labels.final_pickup + ": " + details.pickup_time + "</p>";
//                        comment += "<p>"+ that.config.labels.taxi_number + ": " + details.taxi_number +"</p>";
                        comment += "<p>" + that.config.labels.taxi_station + ": " + details.station_name + " " + details.station_phone + "</p>";
                    }

                    $ride_page.find(".ride_details_comment").empty().append(comment);

                }
                $.mobile.changePage($ride_page);
            }
        });


    },
    cancelOrder: function(order_id) {
        var that = this;
        var $details_btn = $(that.config.selectors.ride_details_btn);

        $.ajax({
            url: that.config.urls.cancel_order,
            type: "POST",
            data: {order_id: order_id},
            dataType: "json",
            success: function(response) {
                if (response.status == 'cancelled') {
                    $("#ride_li_" + order_id + "," + "#ride_header_" + order_id).remove();
                    $(that.config.selectors.ride_details_list).listview("refresh");
                    alert(that.config.labels.order_cancelled);
                    $.mobile.changePage(that.config.selectors.my_rides_page);
                }
            }
        });
    }
});