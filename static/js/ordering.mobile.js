var OrderingHelper = Object.create({
    config:     {
        resolve_address_url:        "", // '{% url cordering.passenger_controller.resolve_address %}'
        estimation_service_url:     "", // '{% url ordering.passenger_controller.estimate_ride_cost %}'
        resolve_coordinate_url:     "", // '{% url ordering.passenger_controller.resolve_coordinate %}'
        not_a_passenger_response:   "",
        not_a_user_response:        "",
        telmap_user:                "",
        telmap_password:            "",
        messages: {
            finding_location:       "",
            estimation_msg:         "",
            no_location_msg:        "",
            sorry_msg:              "",
            order_sent_msg:         "",
            enter_address:          "",
            are_you_sure:           "",
            try_again:              "",
            no_house_number:        ""
        }

    },
    ACCURACY_THRESHOLD:             250, // meters,
    STATE_RESTORE_TIMEOUT:          1000 * 60 * 3, // 3 minutes
    ADDRESS_FIELD_ID_BY_TYPE:       {
        from:   "id_from_raw",
        to:     "id_to_raw"
    },
    map:                            undefined,
    map_markers:                    {},
    current_flow_state:             'from',
    cache:  {},
    last_position:                  {
        longitude       : "",
        latitude        : ""
    },
    order_confirmed:                false,
    order_button_clicked:           false,
    init:                       function(config) {
        this.config = $.extend(true, {}, this.config, config);
        var that = this,
            cache = this.cache,
            digits_re = new RegExp(/\d+/);

        cache.$from_raw_input       = $("#id_from_raw"),
        cache.$to_raw_input         = $("#id_to_raw"),
        cache.$order_form           = $("#order_form"),
        cache.$order_button         = $("#order_button");
        cache.$finish_verification  = $("#finish_verification");

        cache.$order_button.text(that.config.messages.pick_me_up);

        // setup from input
        cache.$from_raw_input.focus(function () {
            that.switchState('from');
            return true;
        });

        // setup to input
        cache.$to_raw_input.focus(function () {
            that.switchState('to');
            return true;
        });

        // send verification code
        $("#send_code").button().button("disable").mouseup(function() {
            var $button = $(this);
            $button.button("disable").set_button_text(that.config.messages.sending);

            // store current state in case user leaves app to handle SMS
            localStorage.create_date = new Date();
            localStorage.local_phone = $("#local_phone").val();
            localStorage.from_address = JSON.stringify(Address.fromInput($("#id_from_raw")));
            localStorage.to_address = JSON.stringify(Address.fromInput($("#id_to_raw")));

            // do the actual request
            $.ajax({
                url         : that.config.send_sms_url,
                type        : 'post',
                data        : $("#verification_form").serialize(),
                success     : function (response) {
                    $("#verification_code").focus();
                },
                error       : function (XMLHttpRequest, textStatus, errorThrown) {
                    alert('error send sms: ' + XMLHttpRequest.responseText);
                },
                complete    : function() {
                    $button.set_button_text(that.config.messages.code_sent)
                }
            });
        });

        // finish verification
        cache.$finish_verification.button().button("disable"); // disabled by default
        $("#verification_code").keyup(function() {
            if ($(this).val().length == 4) {
                cache.$finish_verification.button("enable");
            } else {
                cache.$finish_verification.button("disable");
            }
        });
        cache.$finish_verification.click(function() {
            $.ajax({
                url :that.config.validate_phone_url,
                type : 'post',
                data : $("#verification_form").serialize(),
                success : function (response) {
                    localStorage.clear();
                    $.mobile.changePage("#home");
                    that.bookOrder();
                },
                error :function (XMLHttpRequest, textStatus, errorThrown) {
                    alert(XMLHttpRequest.responseText);
                    $("#send_code").button("enable").set_button_text(that.config.messages.send_verification);
                }
            });
        });

        // toolbar setup
        $(".sources_toolbar").hide();

        $("#gps_button").mousedown(function(e) {
            that.setLocationGPS(true);
            $("#id_" + that.current_flow_state + "_raw").blur(); // collapse the keyboard 
            return false; // don't trigger the change event on the input fields
        });

        // text fields
        $("#home input[type=search]").each(function(i, element) {
            
            var address_type = Address.fromInput(element).address_type;
            $(element).data("address_type", address_type);
            // add clear button
            $(element).after($("<span class='clear'></span>").mousedown(function(e) {
                $(element).val("");
                that.validateForBooking();
                return false; // prevent stealing focus from the input field
            }));
            
            $(element).change(function(e) {
                var val = $(element).val();
                that.validateForBooking();

                that.order_confirmed = false;
                
                if (! val) {
                    return;
                }

                if (val.match(digits_re) == null) { // no matches
                    alert(that.config.messages.no_house_number);
                    $(element).focus();
                    return;
                }

                var lon, lat,
                    other_address = Address.fromInput($("#home input[type=search]")[(i + 1) % 2]); // get the other address

                if (address_type == 'from') {
                    if (that.last_position.longitude && that.last_position.latitude) { // get the last GPS position
                        lon = that.last_position.longitude;
                        lat = that.last_position.latitude;
                    } else { // get location from other address
                        lon = other_address.lon;
                        lat = other_address.lat;
                    }
                } else {
                    if (other_address.lon && other_address.lat) {
                        lon = other_address.lon;
                        lat = other_address.lat;
                    } else { // get location from other address
                        lon = that.last_position.longitude;
                        lat = that.last_position.latitude;
                    }
                }

                var params = { "term": val, "lon": lon, "lat": lat };
                if ($("#resolve_addresses ul li").length) {
                    $("#resolve_addresses ul").empty().listview("refresh");
                }
                $.mobile.changePage("#resolve_addresses");
                $.mobile.pageLoading();
                $.ajax({
                        url: that.config.resolve_address_url,
                        data: params,
                        dataType: "json",
                        success: function(resolve_results) {
                            if (resolve_results.geocode.length == 0) {
                                $.mobile.changePage("#home");
                                alert(that.config.messages.could_not_resolve);
                                // handle unresolved addresses
                            } else {
                                $("#resolve_addresses ul").empty();
                                // render results
                                $.each(resolve_results.geocode, function(i, item) {
                                    var address = Address.fromServerResponse(item, address_type),
                                        $link = $("<a href='#'></a>").text(item.name).click(function() {
                                            that.updateAddressChoice(address);
                                            $.mobile.changePage("#home");
                                        }),
                                        $li = $("<li></li>").append($link);
                                    $("#resolve_addresses ul").append($li).listview("refresh");
                                });
                            }
                        },
                        complete: function() {
                            $.mobile.pageLoading(true);
                        }
                    });

            });
        });



        // $("input:button, input:submit, button").button();

        $("#close_estimate").click(function() {
            $("#ride_cost_estimate").addClass("fade");
        });
        $(".cancel_button").click(function() {
            var address = Address.fromInput($(this).prev().children()[0]);
            if (!address.isResolved()) {
                address.clearFields(true);
            }
            that.switchState();
            that.hideGlassPane();
        });

        $("#local_phone").keyup(function() {
            if ($(this).val()) {
                $("#send_code").button("enable");
            } else {
                $("#send_code").button("disable");
            }
        });

        cache.$order_button.click(function () {
            that.order_button_clicked = true;
            cache.$order_form.submit();
        });

        cache.$order_form.submit(function() {
            if (cache.$order_button.is(':disabled') || !that.order_button_clicked) {
                return false;
            }
            if (! that.order_confirmed) {
                if (! confirm(that.config.messages.are_you_sure)) {
                    return false;
                }
            }

            that.order_button_clicked = false;
            that.order_confirmed = true;
            
            cache.$order_button.disable();

            cache.$order_button.text(that.config.messages.sending);
            $(this).ajaxSubmit({
                dataType: "json",
                complete: function() {
                    that.validateForBooking();
                    cache.$order_button.text(that.config.messages.pick_me_up);
                },
                success: function(order_status) {
                    setTimeout(function() {
                        if (order_status.status == "booked") {
                            alert(order_status.message.split(/<br>/i).join("\n"));
                        } else {
                            alert($("<div></div>").html(order_status.errors.message).text()); // stip html and show message
                        }
                    }, 100);
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    if (XMLHttpRequest.status == 403) {
                        $.mobile.changePage("#sms_dialog");
                    } else {
                        alert(XMLHttpRequest.responseText);
                    }
                }
            });

            return false;
        }); // submit

        $.fixedToolbars.setTouchToggleEnabled(false);
        
        this.validateForBooking();
        setTimeout(function() {
            that.initMap();
            if (!that.restoreState()) {
                that.setLocationGPS(false);
            }
            that.initPoints();
        }, 700);

        return this;
    }, // init
    _setState:              function(active_input, other_input) {
        var that = this;
        window.setTimeout(function() {
            that.hideGlassPane();
            other_input.parent().hide();
            active_input.siblings(".clear").show().parent().addClass("shorter").next().addClass("visible");
            $("#gps_button").removeClass(other_input.data("address_type")).addClass(active_input.data("address_type"));
            $(".sources_toolbar").show();
        }, 10);
    },
    restoreState:           function() {
        var that = this;
        if (localStorage.create_date &&
            (new Date() - Date.parse(localStorage.create_date)) <= that.STATE_RESTORE_TIMEOUT) {
            Address.fromJSON(localStorage.from_address).populateFields();
            Address.fromJSON(localStorage.to_address).populateFields();
            that.validateForBooking();
            $("#local_phone").val(localStorage.local_phone);
            $.mobile.changePage("#sms_dialog");
            $("#verification_code").focus();
            return true;
        }
        return false;
    },
    switchState:            function (enter_state) {
        var $input = undefined,
            that = this;
        this.current_flow_state = enter_state;
        switch ( enter_state ) {
            case 'from':
                that._setState(that.cache.$from_raw_input, that.cache.$to_raw_input);
                break;
            case 'to':
                that._setState(that.cache.$to_raw_input, that.cache.$from_raw_input);
                break;
            default:
                $(".sources_toolbar").hide();
                this.current_flow_state = '';
                this.cache.$to_raw_input.parent().removeClass("shorter").show().next().removeClass("visible");
                this.cache.$from_raw_input.parent().removeClass("shorter").show().next().removeClass("visible");
                $(".clear").hide();
        }
        return this;
    },
    showGlassPane:              function(options) {
        $(".glass_pane > #top").empty().addClass(options.style);
        $(".glass_pane > #bottom").empty().text(options.message);

        $(".glass_pane").addClass("show");
        $("#gps_button").addClass("active")
    },
    hideGlassPane:              function() {
        $("#gps_button").removeClass("active");
        $(".glass_pane").removeClass("show");
    },
    showLocationError:          function(watch_id) {
        navigator.geolocation.clearWatch(watch_id); // remove watch
        var that = this,
            cancel_button = $("<button></button>").text(that.config.messages.enter_address).click(function() {
                $("#id_" + that.current_flow_state + "_raw").focus();
            }),
            try_again_button = $("<button></button>").text(that.config.messages.try_again).click(function() {
                that.setLocationGPS(true);
            }),
            buttons = $("<div class='buttons'></div>").append(cancel_button).append(try_again_button);

        $(".glass_pane > #top").text(that.config.messages.sorry_msg).removeClass("loading");
        $(".glass_pane > #bottom").text(that.config.messages.no_location_msg).append(buttons);
    },
    locationSuccess:            function(position, watch_id) {
        if (console) {
            console.log("new position: " + position.coords.longitude + ", " + position.coords.latitude + " (" + position.coords.accuracy + ")");
        }
        var that = this;
        that.last_position = position.coords;
        if (position.coords.accuracy < that.ACCURACY_THRESHOLD ) {
            navigator.geolocation.clearWatch(watch_id); // we have an accurate enough location
            that.resolveLonLat(position.coords.longitude, position.coords.latitude, that.current_flow_state);
            if (that.map) {
                that.map.setCenter(new telmap.maps.LatLng(position.coords.latitude, position.coords.longitude));
            }
        }
    },
    setLocationGPS:             function(showGlassPane) {
        var that = this;
        var options = {
            timeout             : 5000, // 10 second
            enableHighAccuracy  : true,
            maximumAge          : 0 // always get new location
        };

        if (navigator.geolocation) {
            if (showGlassPane) {
                that.showGlassPane({style: "loading", message: that.config.messages.finding_location});
            }

            var watch_id = navigator.geolocation.watchPosition(function(p) {
                that.locationSuccess.call(that, p, watch_id);
            }, function() {
                that.showLocationError.call(that, watch_id);
            }, options);
        }
    },
    resolveLonLat:              function(lon, lat, address_type) {
        var that = this;
        $.ajax({
                url         : that.config.resolve_coordinate_url,
                type        : "GET",
                data        : { lat: lat,
                        lon: lon  },
                dataType    : "json",
                success     : function(resolve_result) {
                    if (resolve_result) {
                        var new_address = Address.fromServerResponse(resolve_result, address_type);
                        if (new_address.street_address) {   // only update to new address if it contains a valid street

                            that.updateAddressChoice(new_address);
                        }
                    }
                },
                complete    : function() {
                    that.hideGlassPane();
                }
            });
    },
    initMap:                    function () {
        this.initMapSize();
        var prefs = {
            mapTypeId:telmap.maps.MapTypeId.ROADMAP,
            navigationControl:false,
            zoom:15,
            center:new telmap.maps.LatLng(32.09279909028302,34.781051985221),
            login:{
                contextUrl: 'api.navigator.telmap.com/telmapnav',
                userName:   this.config.telmap_user,
                password:   this.config.telmap_password,
                languages:  ['he', 'en'],
                appName:    'wayBetter'
            }
        };
        this.map = new telmap.maps.Map(document.getElementById("map"), prefs);
        window.onresize = function(){ telmap.maps.event.trigger(this.map, "resize"); };
    },
    initMapSize:            function () {
        var map_height;
        map_height = window.innerHeight - $("#gray_header").height();

//        alert(map_height);
        $("#map").css({height: map_height + "px" });
    },
    initPoints:                 function () {
        for (var address_type in this.ADDRESS_FIELD_ID_BY_TYPE) {
            var address = Address.fromFields(address_type);

            if (address.lon && address.lat) {
                this.addPoint(address);
            }
        }
    },
    addPoint:                   function (address) {
        var that = this,
            location_name = address.address_type + ": <br/>" + address.raw,
            icon_image = new telmap.maps.MarkerImage("/static/images/mobile/" + address.address_type + "_map_marker.png", {x:46, y: 43}, undefined, {x:5, y:43}),
            point = new telmap.maps.Marker({
                map:        this.map,
                position:   new telmap.maps.LatLng(address.lat, address.lon),
                draggable:  true,
                icon:       icon_image,
                title:      'Marker'
            });

        $('#id_' + address.address_type + '_raw').val(address.raw);

        telmap.maps.event.addListener(point, 'dragend', function(e) {
            $.ajax({
                url: that.config.resolve_coordinate_url,
                type: "GET",
                data: { lat: point.getPosition().lat(),
                        lon: point.getPosition().lng()  },
                dataType: "json",
                success: function(resolve_result) {
                    var new_address = Address.fromServerResponse(resolve_result, address.address_type);
                    if (new_address.street_address) {   // only update to new address if it contains a valid street
                        that.updateAddressChoice(new_address);
                        $('#id_' + address.address_type + '_raw').effect("highlight", 2000);
                    } else {                    // set previous address
                        that.updateAddressChoice(address);
                    }
                }
            });
        });
        point.location_name = location_name; // monkey patch point
        if (this.map_markers[address.address_type]) {
            this.map_markers[address.address_type].setMap(); // remove old marker from map
        }
        this.map_markers[address.address_type] = point;
        this.renderMapMarkers();
    },
    renderMapMarkers:           function () {
        var that = this,
            map = this.map,
            bounds = new telmap.maps.LatLngBounds();
        
        $.each(this.map_markers, function (i, point) {
            bounds.extend(point.getPosition());
        });

        if (that.map_markers.to && that.map_markers.from) {
            map.fitBounds(bounds);
            map.panToBounds(bounds);
            map.setZoom(map.getZoom() - 1);
        } else if (bounds.valid) {
            map.panTo(bounds.getCenter());
        }
    },
    updateAddressChoice:        function(address) {
        this.hideGlassPane();
        this.switchState();
        address.populateFields();
        this.addPoint(address);
        this.getRideCostEstimate();
        this.validateForBooking();
        if (address.address_type === 'from') {
            $('#from_raw_result').text(this.cache.$from_raw_input.val());
            $("#ride_cost_estimate").removeClass("fade");
        } else {
            $('#to_raw_result').text(this.cache.$to_raw_input.val());
        }
    },
    getRideCostEstimate:        function() {
        var that = this,
            from_lon = $("#id_from_lon").val(),
            from_lat = $("#id_from_lat").val(),
            to_lon = $("#id_to_lon").val(),
            to_lat = $("#id_to_lat").val(),
            from_city = $("#id_from_city").val(),
            to_city = $("#id_to_city").val();

        if (from_lon && from_lat && to_lon && to_lat) {
            $.ajax({
               url: that.config.estimation_service_url,
               type: 'get',
               dataType: 'json',
               data: { from_lon: from_lon, from_lat: from_lat, to_lon: to_lon, to_lat: to_lat,
                       from_city: from_city, to_city: to_city},
               success: that.renderRideEstimatedCost
            });
        }
    },
    renderRideEstimatedCost:    function (data) {
        $("#ride_cost_estimate > .header").text(data.label);
        if (data.estimated_cost && data.estimated_duration){
            var details = data.currency + data.estimated_cost + " (" + data.estimated_duration + ")";
            $("#ride_cost_estimate > .details").text(details);
        }
        $("#ride_cost_estimate").removeClass("fade");
    },
    validateForBooking:         function() {
        for (var address_type in this.ADDRESS_FIELD_ID_BY_TYPE) {
            var address = Address.fromFields(address_type);
            if (!address.isResolved()) {
                address.clearFields();
                if (this.map_markers[address.address_type]) {
                    this.map_markers[address.address_type].setMap();
                    delete this.map_markers[address.address_type];
                }
                this.renderMapMarkers();
                $("#ride_cost_estimate > .header").text(this.config.messages.estimation_msg);
                $("#ride_cost_estimate > .details").empty();
                if (address_type == 'from') {
                    this.cache.$order_button.disable(); // disable ordering if from is not resolved
                    return;
                }

            }
        }
        this.cache.$order_button.enable(); // enable ordering
    },
    bookOrder:              function () {
        this.cache.$order_button.enable(); // otherwise the form would not submit
        this.cache.$order_button.click();
    }
});

