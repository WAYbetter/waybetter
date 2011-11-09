var MyRidesHelper = Object.create({
    config: {
        rtl: false,
        urls: {
            get_myrides_data: "",
            get_order_status: "",
            cancel_order: ""
        },
        messages: {
            ride_cancelled: ""
        },
        order_types: {},
        next_rides_table: undefined,
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

        var $info = $('<td class="info' + ((is_next) ? '"' : ' report"') + '></td>').tooltip({
            tip: this.config.tip,
            position: (this.config.rtl) ? 'center right' : 'center left',
            relative: true,
            offset: [-30,0],
            events: {
                def: ","
            }
        }).click(function() {
            (is_next) ? that._showStatusTooltip(this, order.id) : that._showReportTooltip(this, order.id);
        }).appendTo($row);

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
                    $(that.config.tip_content.pending).find("#cancel_ride_link").click(function() {
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

            tip.find(".close").click(function(){
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
            success: function(){
                $link.removeClass("wb_link").text(that.config.messages.ride_cancelled);
                $tip.find(".close").click(function() {
                    $(info_el).data("tooltip").hide();
                    $(info_el).parent("tr").fadeOut("fast");
                });
            }
        });
    }
});

var HotspotHelper = Object.create({
    config: {
        selectors: {
            hotspotpicker: undefined,
            datepicker: undefined,
            timepicker: undefined
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
            error: options.error
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
        this.cache.dates = [];
        this.cache.months = [];

        $datepicker.datepicker("destroy").datepicker({
            dateFormat: 'dd/mm/yy',
            firstDay: 0,
            minDate: new Date(),
            isRTL: true,
            beforeShowDay: function(date) {
                return ($.inArray(date.toDateString(), that.cache.dates) !== -1) ? [true, "", ""] : [false, "", ""];
            },
            onChangeMonthYear: that._onChangeMonthYear
        });

        $timepicker.empty().disable();
        $hotspotpicker.empty().change(function() {
            var $selected = $hotspotpicker.find(":selected").eq(0);
            if ($selected) {
                var date = getFullDate($selected.data("next_datetime") || new Date());
                $datepicker.datepicker("setDate", date);
                that.refreshHotspotSelector({
                    refresh_intervals: true
                });
            }
        });

        this.getHotspotData({
            beforeSend: function() {
                $hotspotpicker.empty().disable().append("<option>" + that.config.labels.updating + "</option>");
            },
            success: function(response) {
                $hotspotpicker.empty().enable();
                $.each(response.data, function(i, hotspot) {
                    var data = {id: hotspot.id, lon: hotspot.lon, lat: hotspot.lat, next_datetime: new Date(hotspot.next_datetime)};
                    $("<option>" + hotspot.name + "</option>").attr("value", hotspot.id).data(data).appendTo($hotspotpicker);
                });
                $hotspotpicker.change();
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
            this.getIntervals({
                data: $.extend(true, {'day': $datepicker.val(), 'hotspot_id': $hotspotpicker.val()},
                        options.get_intervals_data),
                beforeSend: function() {
                    $timepicker.empty().disable().append("<option>" + that.config.labels.updating + "</option>");
                    if (!$datepicker.val()) {
                        $datepicker.datepicker("setDate", new Date());
                    }
                },
                success: function(response) {
                    if (response.times) {
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
                    flashError("Error loading hotspot times data");
                }
            });
        }
    },

    _onChangeMonthYear: function(year, month, inst) {
        var that = HotspotHelper;
        if ($.inArray(month, that.cache.months) < 0) {
            // get dates for this month
            that.getDates({
                data: {'month': month, 'year': year, 'hotspot_id': $(that.config.selectors.hotspotpicker).val()},
                success: function(response) {
                    var new_dates = $.map(response.dates, function(date, i) {
                        return (new Date(date)).toDateString();
                    });
                    that.cache.dates = that.cache.dates.concat(new_dates);
                    that.cache.months[that.cache.months.length] = month;
                    inst.input.datepicker("refresh");
                },
                error: function() {
                    flashError("Error loading hotspot dates data");
                }
            });
        }
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
    },
    distance    : function(lat1, lon1, lat2, lon2) {
        var p1 = new LatLon(lat1, lon1);
        var p2 = new LatLon(lat2, lon2);

        return p1.distanceTo(p2);
    }
});

/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */
/*  Latitude/longitude spherical geodesy formulae & scripts (c) Chris Veness 2002-2011            */
/*   - www.movable-type.co.uk/scripts/latlong.html                                                */
/*                                                                                                */
/*  Sample usage:                                                                                 */
/*    var p1 = new LatLon(51.5136, -0.0983);                                                      */
/*    var p2 = new LatLon(51.4778, -0.0015);                                                      */
/*    var dist = p1.distanceTo(p2);          // in km                                             */
/*    var brng = p1.bearingTo(p2);           // in degrees clockwise from north                   */
/*    ... etc                                                                                     */
/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */

/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */
/*  Note that minimal error checking is performed in this example code!                           */
/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */


/**
 * Creates a point on the earth's surface at the supplied latitude / longitude
 *
 * @constructor
 * @param {Number} lat: latitude in numeric degrees
 * @param {Number} lon: longitude in numeric degrees
 * @param {Number} [rad=6371]: radius of earth if different value is required from standard 6,371km
 */
function LatLon(lat, lon, rad) {
  if (typeof(rad) == 'undefined') rad = 6371;  // earth's mean radius in km
  // only accept numbers or valid numeric strings
  this._lat = typeof(lat)=='number' ? lat : typeof(lat)=='string' && lat.trim()!='' ? +lat : NaN;
  this._lon = typeof(lon)=='number' ? lon : typeof(lon)=='string' && lon.trim()!='' ? +lon : NaN;
  this._radius = typeof(rad)=='number' ? rad : typeof(rad)=='string' && trim(lon)!='' ? +rad : NaN;
}


/**
 * Returns the distance from this point to the supplied point, in km
 * (using Haversine formula)
 *
 * from: Haversine formula - R. W. Sinnott, "Virtues of the Haversine",
 *       Sky and Telescope, vol 68, no 2, 1984
 *
 * @param   {LatLon} point: Latitude/longitude of destination point
 * @param   {Number} [precision=4]: no of significant digits to use for returned value
 * @returns {Number} Distance in km between this point and destination point
 */
LatLon.prototype.distanceTo = function(point, precision) {
  // default 4 sig figs reflects typical 0.3% accuracy of spherical model
  if (typeof precision == 'undefined') precision = 4;

  var R = this._radius;
  var lat1 = this._lat.toRad(), lon1 = this._lon.toRad();
  var lat2 = point._lat.toRad(), lon2 = point._lon.toRad();
  var dLat = lat2 - lat1;
  var dLon = lon2 - lon1;

  var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
          Math.cos(lat1) * Math.cos(lat2) *
          Math.sin(dLon/2) * Math.sin(dLon/2);
  var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  var d = R * c;
  return d.toPrecisionFixed(precision);
};



/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */


/**
 * Returns the latitude of this point; signed numeric degrees if no format, otherwise format & dp
 * as per Geo.toLat()
 *
 * @param   {String} [format]: Return value as 'd', 'dm', 'dms'
 * @param   {Number} [dp=0|2|4]: No of decimal places to display
 * @returns {Number|String} Numeric degrees if no format specified, otherwise deg/min/sec
 *
 * @requires Geo
 */
LatLon.prototype.lat = function(format, dp) {
    if (typeof format == 'undefined') return this._lat;

    return Geo.toLat(this._lat, format, dp);
};

/**
 * Returns the longitude of this point; signed numeric degrees if no format, otherwise format & dp
 * as per Geo.toLon()
 *
 * @param   {String} [format]: Return value as 'd', 'dm', 'dms'
 * @param   {Number} [dp=0|2|4]: No of decimal places to display
 * @returns {Number|String} Numeric degrees if no format specified, otherwise deg/min/sec
 *
 * @requires Geo
 */
LatLon.prototype.lon = function(format, dp) {
    if (typeof format == 'undefined') return this._lon;

    return Geo.toLon(this._lon, format, dp);
};

/**
 * Returns a string representation of this point; format and dp as per lat()/lon()
 *
 * @param   {String} [format]: Return value as 'd', 'dm', 'dms'
 * @param   {Number} [dp=0|2|4]: No of decimal places to display
 * @returns {String} Comma-separated latitude/longitude
 *
 * @requires Geo
 */
LatLon.prototype.toString = function(format, dp) {
    if (typeof format == 'undefined') format = 'dms';

    if (isNaN(this._lat) || isNaN(this._lon)) return '-,-';

    return Geo.toLat(this._lat, format, dp) + ', ' + Geo.toLon(this._lon, format, dp);
};

/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */

// ---- extend Number object with methods for converting degrees/radians

/** Converts numeric degrees to radians */
if (typeof(Number.prototype.toRad) === "undefined") {
    Number.prototype.toRad = function() {
        return this * Math.PI / 180;
    }
}

/** Converts radians to numeric (signed) degrees */
if (typeof(Number.prototype.toDeg) === "undefined") {
    Number.prototype.toDeg = function() {
        return this * 180 / Math.PI;
    }
}

/**
 * Formats the significant digits of a number, using only fixed-point notation (no exponential)
 *
 * @param   {Number} precision: Number of significant digits to appear in the returned string
 * @returns {String} A string representation of number which contains precision significant digits
 */
if (typeof(Number.prototype.toPrecisionFixed) === "undefined") {
    Number.prototype.toPrecisionFixed = function(precision) {
        if (isNaN(this)) return 'NaN';
        var numb = this < 0 ? -this : this;  // can't take log of -ve number...
        var sign = this < 0 ? '-' : '';

        if (numb == 0) {  // can't take log of zero, just format with precision zeros
            var n = '0.';
            while (precision--) n += '0';
            return n
        }

        var scale = Math.ceil(Math.log(numb) * Math.LOG10E);  // no of digits before decimal
        var n = String(Math.round(numb * Math.pow(10, precision - scale)));
        if (scale > 0) {  // add trailing zeros & insert decimal as required
            l = scale - n.length;
            while (l-- > 0) n = n + '0';
            if (scale < n.length) n = n.slice(0, scale) + '.' + n.slice(scale);
        } else {          // prefix decimal and leading zeros if required
            while (scale++ < 0) n = '0' + n;
            n = '0.' + n;
        }
        return sign + n;
    }
}

/** Trims whitespace from string (q.v. blog.stevenlevithan.com/archives/faster-trim-javascript) */
if (typeof(String.prototype.trim) === "undefined") {
    String.prototype.trim = function() {
        return String(this).replace(/^\s\s*/, '').replace(/\s\s*$/, '');
    }
}
