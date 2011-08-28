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

        $.ajax({
            url: that.config.urls.get_hotspot_data,
            type: "POST",
            dataType: "json",
            success: function(response) {
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