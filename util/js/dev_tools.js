bookTestRide = function () {
    var now = new Date();
    var data = {
        hotspot_date:getFullDate(now),
        hotspot_id:4008,
        hotspot_time:getFullTime(new Date(now.setHours(now.getHours() + 1))),
        hotspot_type:"pickup",
        house_number:"1",
        id_city:"485",
        lat:32.058662,
        lon:34.78742,
        num_seats:"1",
        ride_duration:735,
        street_address:"מרגולין",
        time_type:"pickup"
    };

    $.ajax({
        url:"/book_ride/",
        data:data,
        type:"POST",
        beforeSend:function () {
            $("#book_ride").disable().text("שולח...");
        },
        success:function (response) {
            if (response.status == "booked" && response.redirect)
                window.location.href = response.redirect;
            else {
                showError(response.message || err_msg, function () {
                    $("#book_ride").enable().text(BookingHelper.messages.book_ride);
                    if (response.redirect) {
                        window.location.href = response.redirect;
                    }
                });
            }
        },
        error:function () {
            $("#book_ride").enable().text(BookingHelper.messages.book_ride);
            showError(err_msg, undefined);
        }
    });
};