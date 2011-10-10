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
        update_on_dateselect: true,
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
    hotspot_selector: undefined,
    hotspot_datepicker: undefined,
    hotspot_timepicker: undefined,

    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);
        this.MapHelper = config.MapHelper || CMHelper;
    },

    makeHotSpotSelector: function(hotspot_selector, datepicker_selector, times_selector) {
        var that = this;
        this.cache.dates = [];
        this.cache.months = [];

        this.hotspot_datepicker = $(datepicker_selector).datepicker("destroy").datepicker({
            dateFormat: 'dd/mm/yy',
            firstDay: 0,
            minDate: new Date(),
            isRTL: true,
            beforeShowDay: function(date) {
                return ($.inArray(date.toDateString(), that.cache.dates) !== -1) ? [true, "", ""] : [false, "", ""];
            },
            onChangeMonthYear: that._onChangeMonthYear,
            onSelect: (that.config.update_on_dateselect) ? function(dateText, inst) {
                that.refreshTimes({'day': dateText});
            } : undefined
        });

        this.hotspot_timepicker = $(times_selector).empty().disable();

        this.hotspot_selector = $(hotspot_selector).empty().change(function() {
            var selected = that.hotspot_selector.find(":selected")[0];
            if ($(selected)) {
                var date = getFullDate($(selected).data("next_datetime") || new Date());
                that.hotspot_datepicker.datepicker("setDate", date);
                that.refreshTimes({'day': date});
            }
        });

        this.refreshData();
    },

    refreshData: function(){
        var that = this;
        $.ajax({
            url: that.config.urls.get_hotspot_data,
            dataType: "json",
            beforeSend: function(){
                that.hotspot_selector.empty().disable().append("<option>" + that.config.labels.updating + "</option>");
            },
            success: function(response) {
                that.hotspot_selector.empty().enable();
                $.each(response.data, function(i, hotspot) {
                    var data = {id: hotspot.id, lon: hotspot.lon, lat: hotspot.lat, next_datetime: new Date(hotspot.next_datetime)};
                    $("<option>" + hotspot.name + "</option>").attr("value", hotspot.id).data(data).appendTo(that.hotspot_selector);
                });
                that.hotspot_selector.change();
            },
            error: function() {
                flashError("Error getting hotspot data");
            }
        });
    },

    refreshTimes: function(data){
        this.hotspot_timepicker.empty().disable().append("<option>" + this.config.labels.updating + "</option>");
        if (!this.hotspot_datepicker.val()) {
            this.hotspot_datepicker.datepicker("setDate", new Date());
        }
        var that = this;
        $.ajax({
            url: that.config.urls.get_hotspot_times,
            dataType: "json",
            data: $.extend(true, {'day': that.hotspot_datepicker.val(), 'hotspot_id': that.hotspot_selector.val()}, data),
            success: function(response) {
                if (response.times) {
                    that.hotspot_timepicker.empty();
                    $.each(response.times, function(i, t) {
                        that.hotspot_timepicker.append("<option>" + t + "</option>");
                    });
                    that.hotspot_timepicker.enable().change();
                    if (response.ride_duration){
                        that.hotspot_timepicker.data("ride_duration", response.ride_duration);
                    }
                }
            },
            error: function() {
                flashError("Error loading hotspot times data");
            }
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
        var selected = this.hotspot_selector.find(":selected")[0];
        var lat = $(selected).data("lat");
        var lon = $(selected).data("lon");
        if (lat && lon && this.MapHelper) {
            var img = this.config.hotspot_markers[marker_type] || this.config.hotspot_markers.generic;
            this.MapHelper.addMarker(lat, lon, {icon_image: img, title: $(selected).text(), marker_name: "hotspot"});
        }
    },

    _onChangeMonthYear: function(year, month, inst) {
        var that = HotspotHelper;
        if ($.inArray(month, that.cache.months) < 0) {
            // get dates for this month
            $.ajax({
                url: that.config.urls.get_hotspot_dates,
                dataType: "json",
                data: {'month': month, 'year': year, 'hotspot_id': that.hotspot_selector.val()},
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