var MyRidesHelper = Object.create({
    config: {
        rtl: false,
        urls: {
            get_myrides_data: "",
            get_order_status: "",
            cancel_order: ""
        },
        messages: {
            ride_cancelled: "",
            cancel_link: ""
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

    init: function(config){
        this.config = $.extend(true, {}, this.config, config);
    },

    getData: function(data, callbacks){
        var that = this;
        $.ajax({
            url: that.config.urls.get_myrides_data,
            dataType: "json",
            data: data,
            success: function(data){
                var has_next = (data.next_rides || []).length > 0;
                var has_previous = (data.previous_rides || []).length > 0;
                var $next_table = $(that.config.next_rides_table).eq(0);
                var $previous_table = $(that.config.previous_rides_table).eq(0);

                if ($next_table && has_next) {
                    $.each(data.next_rides, function(i, order) {
                        var row = that._renderRideRow(order, true);
                        $next_table.find("tbody").append(row);
                    });
                    $next_table.show();
                }
                else{
                    $next_table.hide();
                }

                if ($previous_table && has_previous){
                    $.each(data.previous_rides, function(i, order) {
                        var row = that._renderRideRow(order, false);
                        $previous_table.find("tbody").append(row);
                    });
                    $previous_table.show();
                }
                else{
                    $previous_table.hide();
                }

                if (callbacks.success) callbacks.success.call(undefined, has_next, has_previous);
            },
            error: (callbacks.error || function(){})
        });
    },

    _renderRideRow: function(order, is_next){
        var that = this;

        var $row = $('<tr data-order_id="' + order.id + '"></tr>');
        switch (order.type){
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
        $row.append('<td>' + order.when + '</td>');
        $row.append('<td>' + order.price + '</td>');

        var $info = $('<td class="info' + ((is_next) ? '"' : ' report"') + '></td>')
                .append('<a class="wb_link">' + this.config.messages.cancel_link + '</a>');
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

    _showStatusTooltip: function(info_el, order_id){
        var that = this;
        $.ajax({
            url: that.config.urls.get_order_status,
            data: {order_id: order_id},
            dataType: "json",
            success: function(response){
                var status = response.status;

                if (status == "completed"){
                    var details = response.details;
                    var tip = $(that.config.tip_content.completed);
                    tip.find("#pickup_time_val").text(details.pickup_time);
                    tip.find("#taxi_number_val").text(details.taxi_number);
                    tip.find("#station_name_val").text(details.station_name + " " + details.station_phone);
                }
                if (status == "pending"){
                    var $cancel_link = $(that.config.tip_content.pending).find("#cancel_ride_link");
                    // since we are re-using the tooltips it is IMPORTANT to unbind old event handlers
                    $cancel_link.unbind("click").click(function() {
                        that._cancelOrder(info_el, order_id);
                    });
                }

                that._showTooltip(info_el, status);
            },
            error: function(){
                that._showTooltip(info_el, "error");
            }
        });
    },

    _showReportTooltip: function(info_el, order_id){
        $(this.config.tip_content.report_ride).find("#report_ride_link").attr("href", "mailto:rides@waybetter.com?subject=Report Ride " + order_id);
        this._showTooltip(info_el, "report_ride");
    },

    _showTooltip: function(info_el, content) {
        $.each(this.config.tip_content, function(status, content){
            $(content).hide();
        });

        var api = $(info_el).data("tooltip");
        if (api) {
            var tip = api.getTip();
            if (! tip) { // initialize tip
                api.show();
                tip = api.getTip();
            }

            tip.find(".close").unbind("click").click(function(){
                api.hide();
            });

            api.hide();
            api.show();
        }

        $(this.config.tip_content[content]).show();
    },

    _cancelOrder: function(info_el, order_id){
        var that = this;
        var $tip = $(that.config.tip_content.pending);
        var $loader = $tip.find(".tooltip_loader");
        var $link = $tip.find("#cancel_ride_link");
        $.ajax({
            url: that.config.urls.cancel_order,
            type: "POST",
            data: {order_id: order_id},
            dataType: "json",
            beforeSend: function(){
                $loader.show();
                $link.addClass("disabled");
            },
            complete: function(){
                $loader.hide();
                $link.removeClass("disabled");
            },
            success: function(response){
                if (response.status == 'cancelled') {
                    $link.removeClass("wb_link").text(that.config.messages.ride_cancelled);

                    // since we are re-using the tooltips it is IMPORTANT to unbind old event handlers
                    $tip.find(".close").unbind("click").click(function() {
                        $(info_el).data("tooltip").hide();
                        var num_rides = $(that.config.next_rides_table).find("tr[data-order_id]").length;
                        if (num_rides === 1) { // this is the only ride
                            $(that.config.next_rides_container).fadeOut("fast");
                        }
                        else {
                            $(info_el).parent("tr").fadeOut("fast");
                        }
                    });
                }else{
                that._showTooltip(info_el, "error");
                }
            },
            error: function(){
                that._showTooltip(info_el, "error");
            }
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
            get_hotspot_times: ""
        },
        labels: {
            choose_date: "",
            updating: ""
        },
        hotspot_markers: {
            generic: "/static/images/hotspot_red_marker.png",
            pickup: "/static/images/wb_site/map_pin_A.png",
            dropoff: "/static/images/wb_site/map_pin_B.png"
        }
    },
    cache: {
        dates: [],
        months: []
    },

    MapHelper: undefined,

    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);
        this.MapHelper = config.MapHelper || CMHelper;
    },

    clearCache: function(){
        this.cache.dates = [];
        this.cache.months = [];
    },

    getHotspotData: function(options){
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

    getIntervals: function(options){
        var that = this;
        $.ajax({
            url: that.config.urls.get_hotspot_times,
            dataType: "json",
            data: options.data,
            beforeSend: options.beforeSend,
            success: options.success,
            error: options.error,
            complete: options.complete || function(){}
        });
    },

    refreshHotspotMarker: function(marker_type) {
        var that = this;
        if (this.MapHelper.mapready) {
            this._refreshHotspotMarker(marker_type);
        }
        else{
            // wait for it..
            $(window).one("mapready", function() {
                that._refreshHotspotMarker(marker_type);
            });
        }
    },

    _refreshHotspotMarker: function(marker_type) {
        var $selected = $(this.config.selectors.hotspotpicker).find(":selected").eq(0);
        var lat = $selected.data("lat");
        var lon = $selected.data("lon");
        if (lat && lon && this.MapHelper) {
            var img = this.config.hotspot_markers[marker_type] || this.config.hotspot_markers.generic;
            this.MapHelper.addMarker(lat, lon, {icon_image: img, title: $selected.text(), marker_name: "hotspot"});
        }
    },

    makeHotSpotSelector: function() {
        var that = this;
        var $hotspotpicker = $(this.config.selectors.hotspotpicker);
        var $datepicker = $(this.config.selectors.datepicker);
        var $timepicker = $(this.config.selectors.timepicker);
        var $hs_description = $(this.config.selectors.hs_description);

        $timepicker.empty().disable();
        $hotspotpicker.empty().change(function() {
            var $selected = $hotspotpicker.find(":selected").eq(0);
            if ($selected) {
                $hs_description.text("").text($selected.data("description"));
                var now = new Date();
                var human_date = getFullDate($selected.data("next_datetime") || now);
                $datepicker.datepicker("destroy").datepicker({
                    dateFormat: 'dd/mm/yy',
                    firstDay: 0,
                    minDate: new Date(),
                    isRTL: true,
                    beforeShowDay: function(date) {
                        return ($.inArray(date.toDateString(), that.cache.dates) !== -1) ? [true, "", ""] : [false, "", ""];
                    },
                    onChangeMonthYear: that._onChangeMonthYear
                }).datepicker("setDate", human_date);
                that.refreshHotspotSelector({
                    refresh_intervals: true
                });
                that.clearCache();
                that._getDatesForMonthYear(now.getFullYear(), now.getMonth() + 1, $datepicker);
            }
        });

        this.getHotspotData({
            beforeSend: function() {
                $hotspotpicker.empty().disable().append("<option>" + that.config.labels.updating + "</option>");
            },
            success: function(response) {
                $hotspotpicker.empty().enable();
                $.each(response.data, function(i, hotspot) {
                    var data = {id: hotspot.id, lon: hotspot.lon, lat: hotspot.lat, description: hotspot.description, next_datetime: new Date(hotspot.next_datetime)};
                    $("<option>" + hotspot.name + "</option>").attr("value", hotspot.id).data(data).appendTo($hotspotpicker);
                });
                $hotspotpicker.change();

                var month = (new Date).getMonth() + 1;
                var year = (new Date).getFullYear();
                that._getDatesForMonthYear(year, month, $datepicker);
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
            var got_times = false;
            this.getIntervals({
                data: $.extend(true, {'day': $datepicker.val(), 'hotspot_id': $hotspotpicker.val()},
                        options.get_intervals_data),
                beforeSend: function() {
                    $timepicker.empty().disable().append("<option>" + that.config.labels.updating + "</option>");
                    if (!$datepicker.val()) {
                        $datepicker.datepicker("setDate", new Date());
                    }
                    if (options.beforeSend) {
                        options.beforeSend();
                    }
                },
                success: function(response) {
                    if (response.times && response.times.length) {
                        got_times = true;
                        $timepicker.empty();
                        $.each(response.times, function(i, t) {
                            $timepicker.append("<option>" + t + "</option>");
                        });
                        $timepicker.enable().change();
                        if (response.ride_duration) {
                            $timepicker.data("ride_duration", response.ride_duration);
                        }
                    }
                },
                error: function() {
                    if (options.error) {
                        options.error();
                    }
                    else{
                        flashError("Error loading hotspot times data");
                    }
                },
                complete: function(){
                    if (options.complete) {
                        options.complete();
                    }
                    if (got_times) {
                        if (options.onGotTimes)
                            options.onGotTimes();
                    }
                    else{
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

    _getDatesForMonthYear: function(year, month, $datepicker){
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
        }
    },

    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);
    },

    makeStructuredAddressInput: function(city_selector, street_input, hn_input, loader) {
        var that = this,
            $street_input = $(street_input),
            $hn_input = $(hn_input),
            $loader = $(loader);

        function _beforeSend(){
            $loader.show();
        }
        function _complete(){
            $loader.hide();
        }
        $street_input.data("resolved", false);
        $street_input.autocomplete({
            autoFocus: true,
            minLength: 2,
            source: function(request, response){
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
                    error: function(){
                        response([]);
                    }
                });
            },
            select: function(event, ui){
                $(this).data({resolved: true, lat: ui.item.lat, lon: ui.item.lon});
                $(this).autocomplete("disable").blur();
                $hn_input.focus();
            }

        });

        $street_input.focus(
                function() {
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
//        city_selector, street_input, hn_input, callbacks
        var that = this,
            $city_selector = $(options.city_selector),
            $street_input = $(options.street_input),
            $hn_input = $(options.hn_input),
            callbacks = options.callbacks;

        function _beforeSend() {
            $.each([$city_selector, $street_input, $hn_input], function(){
                $(this).disable();
            });
            if (callbacks && callbacks.beforeSend) {
                callbacks.beforeSend();
            }
        }

        function _complete() {
            $.each([$city_selector, $street_input, $hn_input], function(){
                $(this).enable();
            });

            if (callbacks && callbacks.complete) {
                callbacks.complete();
            }
        }

        function _resolved(result) {
            if (callbacks && callbacks.resolved) {
                callbacks.resolved(result);
            }
        }

        function _unresolved(errors) {
            if (callbacks && callbacks.unresolved) {
                callbacks.unresolved(errors);
            }
        }

        function _error(){
            if (callbacks && callbacks.error) {
                callbacks.error();
            }
        }

        var query = {"city_id": $city_selector.val(), "street": $street_input.val(), "house_number": $hn_input.val()};
        $.ajax({
            url: that.config.urls.structured_resolve_url,
            data: query,
            dataType: "json",
            beforeSend: _beforeSend,
            complete: _complete,
            success: function(data) {
                if (data.errors){
                    _unresolved(data.errors);
                }
                else {
                    var geocode_result = [];
                    $.each(data.geocoding_results, function(i, result) {
                        if (result.lat && result.lon && result.street_address && result.house_number) { // this is a valid result
                            if (options.return_multiple) {
                                geocode_result.push(result);
                            } else if (result.street_address == query.street && result.house_number == query.house_number) {
                                geocode_result = result;
                                return false; // break;
                            }
                        }
                    });
                    _resolved(geocode_result);
                }
            },
            error: _error
        });
    }

});


var CMHelper = Object.create({
    config: {
        api_key: '',
        map_element: 'cm-map',
        styleId: 45836,
        center_lat: 32.09279909028302,
        center_lon: 34.781051985221,
        icon_image: "/static/images/wb_site/map_pin_A.png",
        icon_size_x: 61,
        icon_size_y: 154
    },
    map: undefined,
    markers: {},
    icon: undefined,
    mapready: false,

    init: function(config){
        var that = this;
        this.config = $.extend(true, {}, this.config, config);

        var cloudmade = new CM.Tiles.CloudMade.Web({
            key: this.config.api_key,
            styleId: this.config.styleId
//            copyright: ""
        });

        this.map = new CM.Map(this.config.map_element, cloudmade);
        this.map.setCenter(new CM.LatLng(this.config.center_lat, this.config.center_lon), 15);

        this.icon = new CM.Icon();
        this.icon.image = this.config.icon_image;
        this.icon.iconSize = new CM.Size(this.config.icon_size_x, this.config.icon_size_y);

        // TODO_WB: why load event is not fired?
        //CM.Event.addListener(this.map, 'load', function() {alert("foo")});
        $(window).oneTime(1e3, function mapLoaded() {
            if (that.map.isLoaded()){
                that.mapready = true;
                $(window).trigger("mapready");
            }
            else{
                mapLoaded();
            }
        });

        window.onresize = function() {
            that.map.checkResize();
        };
    },

    addMarker: function(lat, lon, options){
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

        if (bounds.length > 1){
            var _bounds = new CM.LatLngBounds(bounds);
            this.map.zoomToBounds(_bounds);
        }
        else{
            this.map.setCenter(myMarkerLatLng, zoom);
        }
    },

    addAMarker: function(lat, lon, options){
        options = $.extend(true, {}, options, {icon_image: "/static/images/wb_site/map_pin_A.png", marker_name: "A"});
        this.addMarker(lat, lon, options);
    },
    addBMarker: function(lat, lon, options){
        options = $.extend(true, {}, options, {icon_image: "/static/images/wb_site/map_pin_B.png", marker_name: "B"});
        this.addMarker(lat, lon, options);
    },
    removeMarker: function(marker_name) {
        var that = this;
        if (marker_name == "all") {
            $.each(this.markers, function(i, marker) {
                that.map.removeOverlay(marker);
            });
            that.markers = {};
        }
        else {
            var marker = this.markers[marker_name];
            if (marker) {
                this.map.removeOverlay(marker);
                delete this.markers.marker_name;
            }
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
    addMarker: function(lat, lon){
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

var MobileHelper = Object.create({
    config: {
        urls:{
            resolve_coordinates: "",
            get_hotspot_dates: ""
        },
        callbacks:{
            onNewAddress: function(address){
                if (console){
                    console.log(address);
                }
            },
            noGeolocation: function(){},
            locationError: function(watch_id){
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
    address: undefined,
    hotspot: undefined,
    hotspot_type: "dropoff",
    time_type: "pickup",

    // METHODS
    // -------
    init: function(config){
        this.config = $.extend(true, {}, this.config, config);
    },
    
    getCurrentLocation: function() {
        var that = this;
        var options = {
            timeout: 5000, // 5 second
            enableHighAccuracy: true,
            maximumAge: 0 // always get new location
        };

        if (navigator.geolocation) {
            var watch_id = navigator.geolocation.watchPosition(function(p) {
                        that.locationSuccess.call(that, p, watch_id);
                    }, function() {
                        that.config.callbacks.locationError(watch_id);
                    }, options);
        } else {
            this.config.callbacks.noGeolocation();
        }
    },
    locationSuccess: function(position, watch_id) {
        if (console) {
            console.log("new position: " + position.coords.longitude + ", " + position.coords.latitude + " (" + position.coords.accuracy + ")");
        }

        this.last_position = position.coords;
        if (position.coords.accuracy < this.ACCURACY_THRESHOLD) {
            navigator.geolocation.clearWatch(watch_id); // we have an accurate enough location
            this.resolveLonLat(position.coords.longitude, position.coords.latitude);
            if (this.MapHelper) {
                this.MapHelper.addMarker(position.coords.latitude, position.coords.longitude);
            }
        }
    },
    resolveLonLat: function(lon, lat) {
        var that = this;
        $.ajax({
            url:that.config.urls.resolve_coordinates,
            type:"GET",
            data:{ lat:lat, lon:lon },
            dataType:"json",
            success:function(address) {
                if (address && address.street_address) {
                    that.config.callbacks.onNewAddress(address);
                }
            },
            complete:function() {
            }
        });
    }
});