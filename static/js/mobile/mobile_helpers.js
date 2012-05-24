/*jslint undef: true, maxerr: 250, indent: 4, browser: true, white: true*/
/*global alert,$,MobileHelper,SocialHelper,HotspotHelper,google,GoogleMapHelper,GoogleGeocodingHelper,getFullDate,log */

'use strict';

var hotspots = [];

var choose_pickup_time_msg  = "{% trans 'Choose Pickup Time' %}";
var choose_dropoff_time_msg = "{% trans 'Choose Dropoff Time' %}";
var pickup_time_msg         = "{% trans 'Pickup Time' %}";
var dropoff_time_msg        = "{% trans 'Dropoff Time' %}";
var pickup_msg              = "{% trans 'Pickup' %}";
var dropoff_msg             = "{% trans 'Dropoff' %}";
var showing_history_select  = false;

function showDialog(dialog_name) {
    alert(dialog_name);
}

function showNoServiceDialog(address) {
    showDialog("{% trans 'Currently we can not offer service in' %} " + address.name);
}

function showError(msg) {
    alert(msg);
}
function showNotification(msg, title) {
    alert(msg);
}

function showErrorDialog(error_msg, title) {
    var $err_dialog_div = $('#error_dialog');
    if ($err_dialog_div.length === 0) {
        $err_dialog_div = $('<div id="error_dialog"><div class="header"></div><div class="body"></div><a href="#" id="focus_link"></a></div>').appendTo('body').hide();
    }
    $err_dialog_div.find('.header').text(title);
    $err_dialog_div.find('.body').text(error_msg);

    $err_dialog_div.fadeIn('slow');

    $err_dialog_div.find('#focus_link').bind('blur', function() {
        $err_dialog_div.fadeOut('fast');
    }).focus();
}

function renderNumseats() {
    var text, label;
    if (MobileHelper.num_seats === 1) {
        text = "{% trans 'One seat' %}";
    } else {
        label = "{% trans 'Seats' %}";
        text = MobileHelper.num_seats + ' ' + label;
    }
    $('#numseats_btn h1').text(text);
}

function resetAddress() {
    MobileHelper.address = undefined;
    $('#choose_address_btn').find('.header').text("{% trans 'Enter Address' %}");
    $('#address-form')[0].reset();
}

// TODO_WB: check hotspot_type to decide where the updated text should go

function resetHotspot() {
    MobileHelper.hotspot = undefined;
    $('#choose_hotspot_btn').find('.header').text("{% trans 'Choose Hotspot' %}");
    $('#choose_hotspot_btn').find('.desc').text('');
}

function showHotspot(hotspot) {
    var $date_sel = $('#select_date');
    addMarker({
        name: hotspot.address,
        lat: hotspot.lat,
        lon: hotspot.lon,
        type: 'hotspot'
    }, true);

    $('#leave_hs_btn').set_button_text('לצאת מ' + hotspot.name).enable();
    $('#get_to_hs_btn').set_button_text('להגיע אל ' + hotspot.name).enable();

    // set hotspot dates
    $date_sel.empty();
    $.each(hotspot.next_dates, function(i, date) {
        var d = getFullDate(new Date(date)),
            today = getFullDate(new Date()),
            $option = $('<option value="' + d + '">' + ((d === today) ? "{% trans 'Today' %}" : d) + '</option>');
        $date_sel.append($option);
    });
}

function selectHotspot(hotspot) {
    log('select hotspot');
    MobileHelper.hotspot = hotspot;
    MobileHelper.ride_date = undefined;
    MobileHelper.ride_time = undefined;
}

function resetSeats() {
    MobileHelper.num_seats = 1;
    renderNumseats();
}

function dismissHistoryList() {
    $('#history_list').hide();
    $('#history_btn').removeClass('active');
}

function toggleHistoryList() {
    var $address_input_page = $('#address_input_page'),
        list_height = window.screen.availHeight - $address_input_page.find('.upper_toolbar_container').height() - $('#history_btn').find('.ui-header').height(),
        $history_list = $('#history_list'),
        used_addresses = {};

    if ($history_list.length === 0) {
        $history_list = $('<div class="pac-container" id="history_list"></div>').appendTo('body').hide();
    }
    $history_list.css({height: list_height + 'px'});

    if ($history_list.is(':visible')) {
        dismissHistoryList();
    } else {
        $history_list.empty();
        $('#history_btn').addClass('active');
        MobileHelper.getRideHistory(function(prev_rides) {
            var addresses = [];
            $.each(prev_rides, function(i, data) {
                $.each(['from', 'to'], function(i, address_type) {
                    if (!used_addresses.hasOwnProperty(data[address_type])) {
                        used_addresses[data[address_type]] = true;
                        addresses.push({
                            name: data[address_type],
                            lon: data[address_type + '_lon'],
                            lat: data[address_type + '_lat']
                        });
                    }
                });
            });

            $.each(addresses, function(i, address) {
                var $item = $('<div class="pac-item"></div>').text(address.name).appendTo($history_list).jqmData('address', address);
                $item.click(function() {
                    dismissHistoryList();
                    updateAddress($(this).jqmData('address'));
                });
            });

            $history_list.show();
        });
    }
}

function bookRide(is_private) {
    var $form = $('<form></form>'),
        hidden_inputs = {
            city_name: MobileHelper.address.city,
            hotspot_date: MobileHelper.ride_date,
            hotspot_id: MobileHelper.hotspot.id,
            hotspot_time: MobileHelper.ride_time,
            hotspot_type: MobileHelper.hotspot_type,
            house_number: MobileHelper.address.house_number,
            is_private: is_private,
            lat: MobileHelper.address.lat,
            lon: MobileHelper.address.lon,
            num_seats: MobileHelper.num_seats,
            order_type: MobileHelper.order_type,
            ride_duration: HotspotHelper.ride_duration,
            street_address: MobileHelper.address.street_address,
            time_type: MobileHelper.hotspot_type
        };

    $.each(hidden_inputs, function(k, v) {
        $form.find("input[name='" + k + "']").remove();
        $form.append($('<input type="hidden"/>').attr('name', k).attr('value', v));
    });

    $.ajax({
        url: '{% url sharing.passenger_controller.book_ride %}',
        data: $form.serialize(),
        type: 'POST',
        beforeSend: function() {
            $('.order_button').disable();
        },
        success: function(response) {
            if (response.status && response.status === 'booked' && response.redirect) {
                if (!response.authenticated) {
                    $.mobile.changePage('#login_or_register_page');
                } else {
                    window.location.href = response.redirect;
                }
            } else {
                //TODO_WB: redirect to error page
                var message = "{% trans 'We have encountered an error. Please try again.' %}";
                if (response.message) {
                    message = response.message;
                }
                showError(message);
                $('.order_button').enable();
            }
        },
        error: function(err) {
            // TODO_WB: show error message/redirect to error page
            showError("{% trans 'We have encountered an error handling your order. Please try again'%}");
            $('.order_button').enable();
        }
    });
}

function clearAddressInput() {
    $('#gac').val('');
    $('#clear_input').hide();
    $('#house_number_bubble').hide();
    GoogleMapHelper.clearMarkers();
    $('#select_address_btn').disable();
}

function handleMissingHouseNumber(result) {
    if (result.address) {
        GoogleMapHelper.setCenter(result.address.lat, result.address.lon);
        var street_name = result.address.street_address,
            $gac = $('#gac'),
            input_value = $gac.val(),
            house_number_start_index = input_value.indexOf(street_name) + street_name.length,
            size = getRenderedSize(street_name + 'I', $gac[0]);


        if (input_value.indexOf(street_name) > -1) {
            $gac.val([input_value.substr(0, house_number_start_index), ' ', input_value.substr(house_number_start_index, input_value.length)].join(''));
            $('#house_number_bubble').css({right: size.width}).fadeIn('fast');
            $gac.one('keydown', function() {
                $('#house_number_bubble').hide();
            });
        }
    }
}

function addMarker(address, zoom) {
    var image_url = '/static/images/mobile/red_marker.png',
        size = new google.maps.Size(10, 10),
        scaled_size = new google.maps.Size(10, 10),
        markerImage = new google.maps.MarkerImage(image_url, size, undefined, new google.maps.Point(5, 5), scaled_size);

    if (window.devicePixelRatio && window.devicePixelRatio >= 2) {
        log('using retina image');
        image_url = '/static/images/mobile/red_marker_retina.png';
        size = new google.maps.Size(20, 20);
    }
    GoogleMapHelper.addMarker(address, {icon: markerImage, marker_name: address.type, show_info: true});

    if (zoom) {
        GoogleMapHelper.setCenter(address.lat, address.lon);
        GoogleMapHelper.map.setZoom(17);
    }
}

function updateAddress(valid_address, lat, lon) {
    clearAddressInput();
    if (valid_address) {
        valid_address.type = 'address';
        $('#gac').val(valid_address.description || valid_address.name);
        $('#clear_input').show();
        addMarker(valid_address, true);
        MobileHelper.address = valid_address;
        $('#select_address_btn').enable();
    } else {
        addMarker({ // fake, unknown address
            lat: lat,
            lon: lon,
            name: 'כתובת לא ידועה',
            type: 'address'
        });
    }
}

function getStartupMessage() {
    $.ajax({
        url: '{% url startup_message %}',
        dataType: 'json',
        success: function(data) {
            if (data && data.show_message) {
                var $message = $(data.page),
                    $page = $('#' + $message.attr('id'));

                $page.html($message.html());
                $page.page();
                $.mobile.changePage($page);
            }
        }
    });
}
function selectInterval() {
    var interval = $(this).jqmData('interval');
    MobileHelper.ride_date = $('#select_date').val();
    MobileHelper.ride_time = interval.time;
    MobileHelper.ride_price = interval.price;
    MobileHelper.order_type = interval.type;
    $.mobile.changePage('#booking_page');
}

function renderIntervals(data) {
    var $list = $('#interval_list');
    $list.empty();
    if (data.intervals) {
        $.each(data.intervals, function(i, interval) {
            var s = '<li><div class="popularity_container"><div class="popularity_text">פופולוריות</div><div class="popularity_meter_bg"><div class="popularity_meter_fg"></div></div><div class="popularity_text">מקסימום <span class="popularity_price"></span> ₪</div></div><a href="#"></a></li>',
                $li = $(s);

            $li.find('.popularity_meter_fg').css({width: interval.popularity * 100 + '%'});
            $li.find('.popularity_price').text(interval.price);
            $li.find('a').jqmData('interval', interval).text(interval.time).click(selectInterval);
            $list.append($li);
        });
        try {
            $list.listview('destroy').listview();
        } catch (e) { } // ignore this
    }
}
function updateTimes(change_page) {
    HotspotHelper.getIntervals({
        data: {
            hotspot_type: MobileHelper.hotspot_type,
            lat: MobileHelper.address.lat,
            lon: MobileHelper.address.lon
        },
        success: function(data) {
            if (!(data.intervals && data.intervals.length > 0)) {
                $.mobile.changePage('#address_input_page');
                showErrorDialog("{% trans 'The service is not operating in your specified address yet. Please try again soon.' %}", "{% trans 'Address Not Covered' %}");
            } else {
                renderIntervals(data);
                if (change_page) {
                    $.mobile.changePage('#select_time_page');
                }
            }
        }
    });
}

function handleHotspotChange() {
    GoogleMapHelper.clearMarkers();
    if (MobileHelper.address) {
        updateTimes(true);
    } else {
        $.mobile.changePage('#address_input_page');
    }
}
function setupMapEvents() {
    // hide error dialog of it's visible
    google.maps.event.addListener(GoogleMapHelper.map, 'mousedown', function() {
        $('#error_dialog:visible').fadeOut('fast');
    });

    google.maps.event.addListener(GoogleMapHelper.map, 'dragstart', function() {
        if ($.mobile.activePage.attr('id') !== 'address_input_page') { return; } // work only on address_input_page

        log('drag start');
        GoogleMapHelper.setMarkersVisibility(false);
        $('#center_target').show();

        GoogleMapHelper.do_drag = true;
    });

    google.maps.event.addListener(GoogleMapHelper.map, 'dragend', function() {
        if ($.mobile.activePage.attr('id') !== 'address_input_page') { return; } // work only on address_input_page

        log('drag end');
        $('#center_target').hide();
        if (GoogleMapHelper.do_drag) {
            clearAddressInput();
            var center = GoogleMapHelper.map.getCenter(),
                input_id = '#gac';

            GoogleGeocodingHelper.reverseGeocodeToPickupAddress(center.lat(), center.lng(), input_id, updateAddress);
        } else {
            GoogleMapHelper.showMarkersByName('address');
        }
    });

    google.maps.event.addListener(GoogleMapHelper.map, 'zoom_changed', function() {
        if ($.mobile.activePage.attr('id') !== 'address_input_page') { return; } // work only on address_input_page

        log('zooom_changed');
        GoogleMapHelper.do_drag = false; // this was a zoom operation
    });
}
function initGoogle() {
    GoogleMapHelper.init({
        map_element: 'map_canvas',
        map_options: {
            center: new google.maps.LatLng(32.115985, 34.835441),
            scrollwheel: false,
            streetViewControl: false,
            keyboardShortcuts: false,
            mapTypeControl: false,
            zoomControl: true,
            mapTypeId: google.maps.MapTypeId.ROADMAP
        }
    });

    GoogleGeocodingHelper.newPlacesAutocomplete({
        id_textinput: 'gac',
        map: GoogleMapHelper.map,
        onMissingStreetNumber: handleMissingHouseNumber,
        onValidAddress: function(address) {
            gac_dirty = false;
            updateAddress(address);
        },

        onNoValidPlace: function() {
            log('onNoValidPlace');
        }
    });

    setupMapEvents();
}
function init() {
    var gac_dirty = false,
        gac_clean_value;

    $('#gac').keydown(function(e) {
        log('gac keydown event', gac_dirty, gac_clean_value);
        if (!gac_dirty) {
            gac_clean_value = $(this).val();
            gac_dirty = true;
        }
    }).blur(function(e) { // done button might have been pressed
        log('gac blur event', gac_dirty, gac_clean_value);
        if (gac_dirty && gac_clean_value) {
            setTimeout(function() {
                $('#gac').val(gac_clean_value);
                log('gac val after change', $('#gac').val());
                gac_dirty = false;
            }, 1);
        }
    }).focus(function() {
        dismissHistoryList();
    });

    log('init');



    $(document).ajaxStart(function() {
        log('ajaxStart');
        $.mobile.showPageLoadingMsg();
    });
    $(document).ajaxStop(function() {
        log('ajaxStop');
        $.mobile.hidePageLoadingMsg();
    });

    // check for startup message
    getStartupMessage();

    // helpers init

    MobileHelper.init({
        urls: {
            resolve_coordinates: '{% url ordering.passenger_controller.resolve_coordinates %}',
            get_myrides_data: '{% url sharing.passenger_controller.get_myrides_data %}',
            cancel_order: '{% url sharing.passenger_controller.cancel_order %}',
            get_order_status: '{% url sharing.passenger_controller.get_order_status %}',
            get_sharing_cities: '{% url get_sharing_cities %}'
        },
        labels: {
            pickup: "{% trans 'From' %}",
            pickupat: "{% trans '_pickupat' %}",
            dropoff: "{% trans 'To' %}",
            price: "{% trans 'Price' %}",
            cancel_ride: "{% trans 'Cancel Ride' %}",
            report_ride: "{% trans 'Report Ride' %}",
            sms_sent: "{% trans 'An SMS notification will be sent (at no charge) prior to your pickup' %}.",
            final_pickup: "{% trans 'Final Pickup Time' %}",
            taxi_number: "{% trans 'Taxi Number' %}",
            taxi_station: "{% trans 'Taxi Station' %}",
            order_cancelled: "{% trans 'Order Cancelled' %}"
        },
        selectors: {
            ride_details_page: '#myride_details_page',
            my_rides_page: '#myrides_page',
            ride_details: '#myride_details_page .ride_summary',
            ride_details_btn: '#ride_details_btn'
        },
        callbacks: {
            locationSuccess: function(position) {
                GoogleMapHelper.setCenter(position.coords.latitude, position.coords.longitude);
                GoogleGeocodingHelper.reverseGeocodeToPickupAddress(position.coords.latitude, position.coords.longitude, '#gac', updateAddress);
                $('#gps_btn').removeClass('active');

            },
            locationError: function() {
                $('#gps_btn').removeClass('active');
                //TODO_WB: handle error
            }
        }
    });

    HotspotHelper.init({
        selectors: {
            hotspotpicker: '#select_hotspot',
            datepicker: '#select_date'
        },
        labels: {
            choose_date: "{% trans 'Choose Date' %}",
            updating: "{% trans 'Updating...' %}"
        },
        urls: {
            get_hotspot_data: '{% url sharing.passenger_controller.get_hotspots_data %}',
            get_hotspot_dates: '{% url sharing.passenger_controller.get_hotspot_dates %}',
            get_hotspot_offers: '{% url sharing.passenger_controller.get_hotspot_offers %}'
        }
    });

    HotspotHelper.getHotspotData({
        data: {numdays: 7},
        beforeSend: function() {
        },
        success: function(response) {
            var $hotspot_list = $('#select_hotspot');
            $hotspot_list.empty();
            $.each(response.data, function(i, hs) {
                hotspots.push(hs);
                var option = $("<option value='" + hs.id + "'>" + hs.name + '</option>').jqmData('hotspot', hs);
                $hotspot_list.append(option);

                if (hotspots.length === response.data.length) {
                    try {
                        $hotspot_list.selectmenu('refresh', true);
                    } catch (e) {
                        // do nothing
                    }
                }
            });
        }
    });

    initGoogle();

    $('#booking_page').bind('pagebeforeshow', function() {
        var first_selector, second_selector, date = MobileHelper.ride_date;
        if (MobileHelper.hotspot_type === 'pickup') {
            first_selector = '#pickup_widget';
            second_selector = '#dropoff_widget';
        } else {
            first_selector = '#dropoff_widget';
            second_selector = '#pickup_widget';
        }
        $(this).find(first_selector).find('.description').text(MobileHelper.hotspot.name);
        $(this).find(first_selector).find('.address').text([MobileHelper.hotspot.address, MobileHelper.hotspot.city_name].join(', '));
        $(this).find('#price_quote .price').text(MobileHelper.ride_price);

        if (MobileHelper.address.description) {
            $(this).find(second_selector).find('.address').text(MobileHelper.address.name);
            $(this).find(second_selector).find('.description').text(MobileHelper.address.description);
        } else {
            $(this).find(second_selector).find('.description').text(MobileHelper.address.name);
            $(this).find(second_selector).find('.address').text('');
        }

        if (getFullDate(new Date()) === date) {
            date = 'היום';
        }
        $(this).find('#time_widget').find('.description').text([date, MobileHelper.ride_time].join(', '));

    });

    $('#choose_pickup_btn').click(function() {
        if (MobileHelper.hotspot_type === 'pickup') {
            $.mobile.changePage('#select_hotspot_page');
        } else {
            $.mobile.changePage('#address_input_page');
        }
    });

    $('#choose_dropoff_btn').click(function() {
        if (MobileHelper.hotspot_type === 'pickup') {
            $.mobile.changePage('#address_input_page');
        } else {
            $.mobile.changePage('#select_hotspot_page');
        }
    });

    $('#address_input_page').bind('pagebeforeshow', function() { // page-before-show
        if (!MobileHelper.address) {
            $(this).find('button').disable();
        }
        var map_div = GoogleMapHelper.map.getDiv();
        $('.map_container', $(this)).append(map_div);
        GoogleMapHelper.showMarkersByName('address');

    }).bind('pagebeforehide', function() { // page-before-hide
        dismissHistoryList();
    });


    $('#select_hotspot_page').bind('pagebeforeshow', function() {
        var map_div = GoogleMapHelper.map.getDiv();
        $('.map_container', $(this)).append(map_div);

        if (!MobileHelper.hotspot) {
            $(this).find('button').set_button_text('-').disable();
            showHotspot(hotspots[0]);
        } else {
            showHotspot(MobileHelper.hotspot);
        }

    }).bind('pageaftershow', function() {
        GoogleMapHelper.showMarkersByName('hotspot');
    });

    $('#select_time_page').bind('pagebeforeshow', function() {
        var list_height = window.screen.availHeight - $(this).find('.upper_toolbar_container').height() - $(this).find('.ui-header').height();
        $('#list_container').css({height: list_height + 'px'});
    });

    $('#select_hotspot').change(function() {
        showHotspot($('#select_hotspot').find('option:selected').jqmData('hotspot'));
    });

    $('#leave_hs_btn').click(function() {
        selectHotspot($('#select_hotspot').find('option:selected').jqmData('hotspot'));
        MobileHelper.hotspot_type = 'pickup';
        handleHotspotChange();
    });

    $('#get_to_hs_btn').click(function() {
        selectHotspot($('#select_hotspot').find('option:selected').jqmData('hotspot'));
        MobileHelper.hotspot_type = 'dropoff';
        handleHotspotChange();
    });

    // booking page

    $('#gac').bind('keyup', function() {
        if ($(this).val()) {
            $('#clear_input').show();
        } else {
            $('#clear_input').hide();
        }
    });

    $('#clear_input').hide().click(clearAddressInput);

    $('#select_address_btn').click(function() {
        updateTimes(true);
    });

    $('#select_date').change(function() {
        updateTimes();
    });

    $('#calculate_ride_btn').click(function() {
        bookRide();
    });

    // numseats page
    $('.choose-numseats').click(function() {
        MobileHelper.num_seats = $(this).data('numseats');
        renderNumseats();
    });

    $('#gps_btn').click(function() {
        $(this).addClass('active');
        dismissHistoryList();
        MobileHelper.getCurrentLocation();
    });

    $('#history_btn').click(toggleHistoryList);

    $('#home').bind('pagebeforeshow', function() {
        MobileHelper.updateMyRidesBubble('#myrides_btn');
    });

    // choose ride page
    $('.order_button').disable();

    $('#select_hotspot_help').click(function() {
        $.mobile.changePage('#select_hotspot_help_page');
    });

    // my rides page
    $('#myrides_page').bind('pagebeforeshow', function(e, data) {
        if ((data.prevPage.attr('id') !== 'myride_details_page')) {
            $('#upcoming_rides_btn').click();
        }
    });
    $('#upcoming_rides_btn').click(function() {
        MobileHelper.getMyRidesData({get_next_rides: true}, '#rides_list');
    });
    $('#ride_history_btn').click(function() {
        MobileHelper.getMyRidesData({get_previous_rides: true}, '#rides_list');
    });

    // share page
    $('#like_fb').click(function(e) {
        window.location.href = SocialHelper.getFacebookLikeLink(true);
        e.preventDefault();
    });

    $('#share_email').click(function() {
        window.location.href = SocialHelper.getEmailShareLink();
    });
}

$(document).one('pageinit', init);
