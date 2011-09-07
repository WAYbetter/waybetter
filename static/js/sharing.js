var HotspotHelper = Object.create({
    config: {
        urls: {
            get_hotspot_data: "",
            get_hotspot_dates: "",
            get_hotspot_times: ""
        },
        labels: {
            choose_date: "",
            updating: ""
        }
    },
    cache: {
        dates: [],
        months: []
    },
    hotspot_selector: undefined,
    hotspot_datepicker: undefined,
    hotspot_timepicker: undefined,

    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);

    },

    makeHotSpotSelector: function(hotspot_selector, datepicker_selector, times_selector) {
        var that = this;
        this.cache.dates = [];
        this.cache.months = [];
        this.hotspot_selector = $(hotspot_selector).empty().change(function() {
            var selected = that.hotspot_selector.find(":selected")[0];
            if ($(selected)) {
                var date = getFullDate($(selected).data("next_datetime") || new Date());
                that.hotspot_datepicker.datepicker("setDate", date);
                that._onDateSelect(date, undefined);
                that.refrestHotspotMarker();
            }
        });
        this.hotspot_datepicker = $(datepicker_selector).datepicker("destroy");
        this.hotspot_timepicker = $(times_selector).empty().disable();

        this.refreshData();

        this.hotspot_datepicker.datepicker({
            dateFormat: 'dd/mm/yy',
            firstDay: 0,
            minDate: new Date(),
            isRTL: true,
            beforeShowDay: function(date) {
                return ($.inArray(date.toDateString(), that.cache.dates) !== -1) ? [true, "", ""] : [false, "", ""];
            },
            onChangeMonthYear: that._onChangeMonthYear,
            onSelect: that._onDateSelect
        })
    },

    refreshData: function(){
        var that = this;
        $.ajax({
            url: that.config.urls.get_hotspot_data,
            type: "POST",
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

    refrestHotspotMarker: function() {
        var selected = this.hotspot_selector.find(":selected")[0];
        var lat = $(selected).data("lat");
        var lon = $(selected).data("lon");
        if (lat && lon) {
            var hotsport_marker_image = '/static/images/hotspot_red_marker.png';
            var hotsport_marker_offset = {x:32, y:63};

            var icon_image = new telmap.maps.MarkerImage(hotsport_marker_image, undefined, undefined, hotsport_marker_offset);
            var point = new telmap.maps.Marker({
                map:        OrderingHelper.map,
                position:   new telmap.maps.LatLng(lat, lon),
                icon:       icon_image,
                title:      "Hotspot"
            });

            OrderingHelper.removePoint("hotspot");
            OrderingHelper.map_markers["hotspot"] = point;
            OrderingHelper.renderMapMarkers();
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
                    alert("Error loading hotspot dates data");
                }
            });
        }
    },

    _onDateSelect: function(dateText, inst) {
        var that = HotspotHelper;
        that.hotspot_timepicker.empty().disable().append("<option>" + that.config.labels.updating + "</option>");
        $.ajax({
            url: that.config.urls.get_hotspot_times,
            dataType: "json",
            data: {'day': dateText, 'hotspot_id': that.hotspot_selector.val()},
            success: function(response) {
                that.hotspot_timepicker.empty();
                $.each(response.times, function(i, d) {
                    that.hotspot_timepicker.append("<option>" + d + "</option>");
                });
                that.hotspot_timepicker.enable().change();
            },
            error: function() {
                alert("Error loading hotspot times data");
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

    makeStructuredAddressInput: function(city_selector, street_input, hn_input) {
        var that = this,
            $street_input = $(street_input),
            $hn_input = $(hn_input);

        $street_input.data("resolved", false);
        $street_input.autocomplete({
            selectFirst: true,
            minLength: 2,
            source: function(request, response){
                $.ajax({
                    url: that.config.urls.structured_resolve_url,
                    data: {"city_id": $(city_selector).val(), "street": $street_input.val(), "house_number": $hn_input.val()},
                    dataType: "json",
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
            select: function(){
                $(this).data("resolved", true);
                $(this).autocomplete("disable").blur();
            }

        });

        $street_input.focus(
                function() {
                    $(this).autocomplete("enable");
                    $(this).autocomplete("search");
                    $(this).data("value", $(this).val());
                }).keyup(function() {
                    if ($(this).data("value") !== $(this).val()) {
                        $(this).data("resolved", false);
                    }
                });
    },

    resolveStructured: function(city_selector, street_input, hn_input, callbacks) {
        var that = this,
            $city_selector = $(city_selector),
            $street_input = $(street_input),
            $hn_input = $(hn_input);

        function _beforeSend() {
            $street_input.siblings(".street_error").text("");
            $hn_input.siblings(".hn_error").text("");
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

        function _resolved() {
            if (callbacks && callbacks.resolved) {
                callbacks.resolved();
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

        var query = {"city_id": $(city_selector).val(), "street": $street_input.val(), "house_number": $hn_input.val()};
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
                    $.each(data.geocoding_results, function(i, result) {
                        if (result.street_address && result.street_address == query.street && result.house_number && result.house_number == query.house_number) {
                            _resolved();
                            return false; // break;
                        }
                    });
                }
            },
            error: _error
        });
    }

});