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
                        $next_table.find("tbody").append(row);
                    });
                    $next_table.show();
                }
                else {
                    $next_table.hide();
                }

                if ($previous_table && has_previous) {
                    $.each(data.previous_rides, function(i, order) {
                        var row = that._renderRideRow(order, false);
                        $previous_table.find("tbody").append(row);
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
                    var $cancel_link = $(that.config.tip_content.pending).find("#cancel_ride_link");
                    // since we are re-using the tooltips it is IMPORTANT to unbind old event handlers
                    $cancel_link.unbind("click").click(function() {
                        that._cancelOrder(info_el, order_id);
                    });
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
                } else {
                    that._showTooltip(info_el, "error");
                }
            },
            error: function() {
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
        $.ajax({
            url: that.config.urls.get_hotspot_times,
            dataType: "json",
            data: options.data,
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

    refreshHotspotMarker: function(marker_type) {
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

    _refreshHotspotMarker: function(marker_type) {
        var $selected = $(this.config.selectors.hotspotpicker).find(":selected").eq(0);
        var lat = $selected.data("lat");
        var lon = $selected.data("lon");
        if (lat && lon && this.MapHelper) {
            var img = this.config.hotspot_markers[marker_type] || this.config.hotspot_markers.generic;
            this.MapHelper.addMarker(lat, lon, {icon_image: img, title: $selected.text(), marker_name: "hotspot"});
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
                        var now = new Date();
                        var first_interval = getFullDate($selected.data("next_datetime") || now);
                        $datepicker.datepicker("destroy").datepicker({
                            dateFormat: 'dd/mm/yy',
                            minDate: new Date(),
                            isRTL: true,
                            beforeShowDay: function(date) {
                                return ($.inArray(date.toDateString(), that.cache.dates) !== -1) ? [true, "", ""] : [false, "", ""];
                            },
                            onSelect: options.onSelectDate,
                            onChangeMonthYear: that._onChangeMonthYear
                        }).datepicker("setDate", first_interval);
                        that.refreshHotspotSelector({
                            refresh_intervals: true
                        });
                        that.clearCache();
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
                data: $.extend(true, {'day': $datepicker.val(), 'hotspot_id': $hotspotpicker.val()},
                        options.get_intervals_data),
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


var CMHelper = Object.create({
    config: {
        api_key: '',
        map_element: 'cm-map',
        styleId: 45836,
        center_lat: 32.09279909028302,
        center_lon: 34.781051985221,
        icon_image: "/static/images/wb_site/map_pin_A.png",
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
        options = $.extend(true, {}, options, {icon_image: "/static/images/wb_site/map_pin_A.png", marker_name: "A"});
        this.addMarker(lat, lon, options);
    },
    addBMarker: function(lat, lon, options) {
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
    this._lat = typeof(lat) == 'number' ? lat : typeof(lat) == 'string' && lat.trim() != '' ? +lat : NaN;
    this._lon = typeof(lon) == 'number' ? lon : typeof(lon) == 'string' && lon.trim() != '' ? +lon : NaN;
    this._radius = typeof(rad) == 'number' ? rad : typeof(rad) == 'string' && trim(lon) != '' ? +rad : NaN;
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

    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1) * Math.cos(lat2) *
                    Math.sin(dLon / 2) * Math.sin(dLon / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
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
