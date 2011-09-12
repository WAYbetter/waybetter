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
                that.refrestHotspotMarker();
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
                alert("Error loading hotspot times data");
            }
        });
    },
    
    refrestHotspotMarker: function() {
        var selected = this.hotspot_selector.find(":selected")[0];
        var lat = $(selected).data("lat");
        var lon = $(selected).data("lon");
        if (lat && lon && window.telmap) {
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
            autoFocus: true,
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
            select: function(event, ui){
                $(this).data({resolved: true, lat: ui.item.lat, lon: ui.item.lon});
                $(this).autocomplete("disable").blur();
//                $hn_input.focus();
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

    resolveStructured: function(city_selector, street_input, hn_input, callbacks) {
        var that = this,
            $city_selector = $(city_selector),
            $street_input = $(street_input),
            $hn_input = $(hn_input);

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
                        if (result.lat && result.lon && result.street_address && result.house_number &&
                                result.street_address == query.street && result.house_number == query.house_number) {

                            _resolved(result);
                            return false; // break;
                        }
                    });
                }
            },
            error: _error
        });
    }

});