function asHotSpotInput(hotspot_selector, datepicker_selector, times_selector, config) {

    var $hotspot = $(hotspot_selector);
    var $datepicker = $(datepicker_selector);
    var $times = $(times_selector);

    $datepicker.data("cached_dates", []);
    $datepicker.data("cached_months", []);
    var cached_dates = $datepicker.data("cached_dates");
    var cached_months = $datepicker.data("cached_months");

    $datepicker.datepicker("destroy");
    $times.empty().disable().append("<option>" + config.labels.choose_date + "</option>");

    function onChangeMonthYear(year, month, inst) {
        if ($.inArray(month, cached_months) < 0) {
            // get dates for this month
            $.ajax({
                url: config.urls.get_hotspot_dates,
                dataType: "json",
                data: {'month': month, 'year': year, 'hotspot_id': $hotspot.val()},
                success: function(response) {
                    var new_dates = $.map(response.dates, function(date, i) {
                        return (new Date(date)).toDateString();
                    });
                    cached_dates = cached_dates.concat(new_dates);
                    cached_months[cached_months.length] = month;
                    inst.input.datepicker("refresh");
                },
                error: function() {
                    alert("Error loading hotspot dates data");
                }
            });
        }
    }

    function onSelect(dateText, inst) {
        $times.empty().disable().append("<option>" + config.labels.updating + "</option>");

        $.ajax({
            url: config.urls.get_hotspot_times,
            dataType: "json",
            data: {'day': dateText, 'hotspot_id': $hotspot.val()},
            success: function(response) {
                $times.empty();
                $.each(response.times, function(i, d) {
                    $times.append("<option>" + d + "</option>");
                });
                $times.enable();
                $times.change();
            },
            error: function() {
                alert("Error loading hotspot times data");
            }
        });
    }

    $datepicker.datepicker({
        dateFormat: 'dd/mm/yy',
        firstDay: 0,
        minDate: new Date(),
        isRTL: true,
        beforeShowDay: function(date) {
            return ($.inArray(date.toDateString(), cached_dates) !== -1) ? [true, "", ""] : [false, "", ""];
        },
        onChangeMonthYear: onChangeMonthYear,
        onSelect: onSelect
    });

    var today = getFullDate(new Date());
    $datepicker.datepicker("setDate", today);
    onSelect(today, undefined);
}
