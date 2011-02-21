var MapMarker = defineClass({
    name: "MapMarker",
    construct:      function(lon, lat, location_name, icon_image, is_center) {
        this.lon = lon;
        this.lat = lat;
        this.location_name = location_name;
        this.icon_image = icon_image;
        this.is_center = is_center;
    }
});

var Address = defineClass({
    name:       "Address",
    construct:  function(name, street, city, country, geohash, lon, lat, address_type) {
        this.name = name;
        this.street = street;
        this.city = city;
        this.country = country;
        this.geohash = geohash;
        this.lon = lon;
        this.lat = lat;
        this.address_type = address_type;
    },
    methods:    {
        isResolved:     function() {
            return (this.lon && this.lat) && (this.name == $('#id_geocoded_' + this.address_type + '_raw').val());
        },
        populateFields: function () {
            $('#id_' + this.address_type + '_raw').val(this.name);
            $('#id_geocoded_' + this.address_type + '_raw').val(this.name);
            $('#id_' + this.address_type + '_city').val(this.city);
            $('#id_' + this.address_type + '_street_address').val(this.street);
            $('#id_' + this.address_type + '_country').val(this.country);
            $('#id_' + this.address_type + '_geohash').val(this.geohash);
            $('#id_' + this.address_type + '_lon').val(this.lon);
            $('#id_' + this.address_type + '_lat').val(this.lat);
        }
    },
    statics:    {
        // factory methods
        fromFields:         function(address_type) {
            var name =      $('#id_' + address_type + '_raw').val(),
                city =      $('#id_' + address_type + '_city').val(),
                street =    $('#id_' + address_type + '_street_address').val(),
                country =   $('#id_' + address_type + '_country').val(),
                geohash =   $('#id_' + address_type + '_geohash').val(),
                lon =       $('#id_' + address_type + '_lon').val(),
                lat =       $('#id_' + address_type + '_lat').val();

            return new Address(name, street, city, country, geohash, lon, lat, address_type);
        },
        fromServerResponse: function(response, address_type) {
             return new Address( response["name"],
                                 response["street"],
                                 response["city"],
                                 response["country"],
                                 response["geohash"],
                                 response["lon"],
                                 response["lat"],
                                 address_type );
        }
    }
});

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
    ACCURACY_THRESHOLD:             250, // meters
    ADDRESS_FIELD_ID_BY_TYPE:       {
        from:   "id_from_raw",
        to:     "id_to_raw"
    },
    map:                            {},
    map_markers:                    {},
    current_flow_state:             'from',
    cache:  {},
    last_position:                  {
        longitude       : "",
        latitude        : ""
    },
    init:                       function(config) {
        this.config = $.extend(true, {}, this.config, config);
        var that = this,
            cache = this.cache;
        cache.$from_raw_input = $("#id_from_raw"),
        cache.$to_raw_input = $("#id_to_raw"),
        cache.$order_form = $("#order_form"),
        cache.$order_button = $("#order_button");
        cache.$finish_verification = $("#finish_verification");
        var digits_re = new RegExp(/\d+/);

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
        $("#send_code").mouseup(function() {
            var $button = $(this);
            $button.button("disable").text(that.config.messages.sending);

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
                    $button.text(that.config.messages.code_sent)
                }
            });
        });
        $("#local_phone").change(function() {
            $("#send_code").button('enable').text(that.config.messages.send_verification);
        });

        // finish verification
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
                    $jqt.goBack();
                    that.bookOrder();
                },
                error :function (XMLHttpRequest, textStatus, errorThrown) {
                    alert(XMLHttpRequest.responseText);
                    $("#send_code").button('enable');
                }
            });
        });


        // toolbar setup
        $(".sources_toolbar").hide();
        $("#gps_button").click(function(e) {
            that.setLocationGPS(true);
            e.preventDefault();
        });

        // text fields
        $("#home input:text").each(function(i, element) {

            var address_type = element.name.split("_")[0];
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

                if (! val) {
                    return;
                }

                if (val.match(digits_re) == null) { // no matches
                    alert(that.config.messages.no_house_number);
                    $(element).focus();
                    return;
                }

                var params = { "term": val, "lon": that.last_position.longitude, "lat": that.last_position.latitude };
                $jqt.goTo("#resolve_addresses", "slideleft");
                $("#resolve_addresses ul").addClass("loading_address").empty().append("<li>" + that.config.messages.looking_for + "</li>");
                $.ajax({
                        url: that.config.resolve_address_url,
                        data: params,
                        dataType: "json",
                        success: function(resolve_results) {
                            if (resolve_results.geocode.length == 0) {
                                $jqt.goBack();
                                alert(that.config.messages.could_not_resolve);
                                // handle unresolved addresses
                            } else {
                                $("#resolve_addresses ul").empty();
                                // render results
                                $.each(resolve_results.geocode, function(i, item) {
                                    var address = Address.fromServerResponse(item, address_type),
                                        $link = $("<a href='#'></a>").text(item.name).click(function() {
                                            that.updateAddressChoice(address);
                                            $jqt.goBack();
                                        }),
                                        $li = $("<li></li>").append($link);
                                    $("#resolve_addresses ul").append($li);
                                });
                            }
                        },
                        complete: function() {
                            $("#resolve_addresses ul").removeClass("loading_address")
                        }
                    });

            });
        });



        $("input:button, input:submit, button").button();

         $("#ride_cost_estimate > .text").text(that.config.messages.estimation_msg).click(function () {
            $jqt.goTo("#sms_dialog", "slideleft");
        });
        $("#close_estimate").click(function() {
            $("#ride_cost_estimate").fadeOut("fast");
        });
        $(".cancel_button").click(function() {
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
        
        cache.$order_button.button("disable").click(function () {
            cache.$order_form.submit();
        });

        cache.$order_form.submit(function() {
            if (cache.$order_button.attr("disabled")) {
                return false;
            }
            if (! confirm(that.config.messages.are_you_sure)) {
                return false;
            }

            cache.$order_button.button("disable");

            $(this).ajaxSubmit({
                dataType: "json",
                complete: function() {
                    that.validateForBooking();    
                },
                success: function(order_status) {
                    if (order_status.status == "booked") {
                        alert(that.config.messages.order_sent_msg);
                    } else {
                        alert($("<div></div>").html(order_status.errors.message).text()); // stip html and show message
                    }
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    if (XMLHttpRequest.status == 403) {
                        $jqt.goTo("#sms_dialog", "slideleft");
                    } else {
                        alert(XMLHttpRequest.responseText);
                    }
                }
            });

            return false;
        }); // submit

        this.initMap();
        this.setLocationGPS(false);

        //TODO_WB:add a check for map, timeout and check again.
        setTimeout(that.initPoints, 100);
        
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
    showLocationError:          function() {
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
    locationSuccess:            function(position) {
        var that = this;
        that.last_position = position.coords;
        if (position.coords.accuracy < that.ACCURACY_THRESHOLD ) {
            that.resolveLonLat(position.coords.longitude, position.coords.latitude, that.current_flow_state);
            that.map.setCenter(new telmap.maps.LatLng(position.coords.latitude, position.coords.longitude));
        } else {
            that.showLocationError();
        }
    },
    setLocationGPS:             function(showGlassPane) {
        var that = this;
        var options = {
            timeout             : 1000, // 1 second
            enableHighAccuracy  : true,
            maximumAge          : 60000 // 1 minute
        };

        if (navigator.geolocation) {
            if (showGlassPane) {
                that.showGlassPane({style: "loading", message: that.config.messages.finding_location});
            }
            navigator.geolocation.getCurrentPosition(function(p) {
                that.locationSuccess.call(that, p);
            }, function() {
                that.showLocationError.call(that);
            }, options);
        }
    },
    resolveLonLat:              function(lon, lat, address_type) {
        var that = this;
        $.ajax({
                url: that.config.resolve_coordinate_url,
                type: "GET",
                data: { lat: lat,
                        lon: lon  },
                dataType: "json",
                success: function(resolve_result) {
                    if (resolve_result) {
                        var new_address = Address.fromServerResponse(resolve_result, address_type);
                        if (new_address.street) {   // only update to new address if it contains a valid street

                            that.updateAddressChoice(new_address);
                        }
                    }
                }
            });
    },
    initMap:                    function () {
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
        this.initMapSize();
    },
    initMapSize:            function () {
        var map_height;
        if ("standalone" in window.navigator && window.navigator.standalone) {
            map_height = $(window).height() - $("#gray_header").height() - $("#bottom_toolbar").height() - 5;
        } else {
            map_height = $(window).height() - $("#gray_header").height() - $("#bottom_toolbar").height() + 50;
        }

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
            location_name = address.address_type + ": <br/>" + address.name,
            icon_image = new telmap.maps.MarkerImage("/static/images/mobile/" + address.address_type + "_map_marker.png", {x:46, y: 43}, undefined, {x:5, y:43}),
            point = new telmap.maps.Marker({
                map:        this.map,
                position:   new telmap.maps.LatLng(address.lat, address.lon),
                draggable:  true,
                icon:       icon_image,
                title:      'Marker'
            });

        $('#id_' + address.address_type + '_raw').val(address.name);

        telmap.maps.event.addListener(point, 'dragend', function(e) {
            $.ajax({
                url: that.config.resolve_coordinate_url,
                type: "GET",
                data: { lat: point.getPosition().lat(),
                        lon: point.getPosition().lng()  },
                dataType: "json",
                success: function(resolve_result) {
                    var new_address = Address.fromServerResponse(resolve_result, address.address_type);
                    if (new_address.street) {   // only update to new address if it contains a valid street
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
        var label = data.label + ":";
        label += data.estimated_cost + data.currency;
        label += " (" + data.estimated_duration + ")";
        $("#ride_cost_estimate > .text").text(label);
    },
    validateForBooking:         function() {
        for (var address_type in this.ADDRESS_FIELD_ID_BY_TYPE) {
            var address = Address.fromFields(address_type);
            if (!address.isResolved()) {
                if (this.map_markers[address.address_type]) {
                    this.map_markers[address.address_type].setMap();
                    delete this.map_markers[address.address_type];
                }
                this.renderMapMarkers();
                $("#ride_cost_estimate > .text").text(this.config.messages.estimation_msg);
                if (address_type == 'from') {
                    this.cache.$order_button.button("disable"); // disable ordering if from is not resolved
                    return;
                }
            }
        }
        this.cache.$order_button.button("enable"); // enable ordering
    },
    bookOrder:              function () {
        this.cache.$order_button.button("enable"); // otherwise the form would not submit
        this.cache.$order_button.click();
    }
});

