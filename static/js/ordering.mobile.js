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

var Registrator = Object.create({

});

var OrderingHelper = Object.create({
    config:     {
        unresolved_label:           "", // "{% trans 'Could not resolve address' %}"
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
            order_sent_msg:         ""
        }

    },
    ACCURACY_THRESHOLD:             200, // meters
    ADDRESS_FIELD_ID_BY_TYPE:       {
        from:   "id_from_raw",
        to:     "id_to_raw"
    },
    map:                            {},
    map_markers:                    {},
    map_markers_popups:             {},
    has_results:                    false,
    current_flow_state:             'from',
    cache:  {
        $from_raw_input : null,
        $to_raw_input   : null,
        $passenger_msg  : null
    },
    init:                       function(config) {
        this.config = $.extend(true, {}, this.config, config);
        var that = this,
            cache = this.cache;
        cache.$from_raw_input = $("#id_from_raw"),
        cache.$to_raw_input = $("#id_to_raw"),
        cache.$passenger_msg = $('#passenger_message'),
        cache.$top_control = $('#top_control'),
        cache.$map_container = $('#map_container'),
        cache.$order_button = $("#order_button"),
        cache.$button_container = $("#button_container");
        cache.$from_raw_input.focus(function () {
            that.switchState('from');
            return true;
        });
        cache.$to_raw_input.focus(function () {
            that.switchState('to');
            return true;
        });

        $("input:button, input:submit").button();

        cache.$order_button.button().button("disable").click(function () {
            $('#order_form').submit();
        });

        $("#order_form").submit(function() {
            if (cache.$order_button.attr("disabled")) {
                return false;
            }

            cache.$order_button.button("disable");

            $(this).ajaxSubmit({
                dataType: "json",
                complete: function() {
                    that.validateForBooking();    
                },
                success: function(order_status) {
//                    clearError();
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
        this.setLocationGPS();

        //TODO_WB:add a check for map, timeout and check again.
        setTimeout(that.initPoints, 100);
        
        return this;
    }, // init

    switchState:            function (enter_state) {
        var $input = undefined,
            that = this;
        this.current_flow_state = enter_state;
        switch ( enter_state ) {
            case 'from':
                window.setTimeout(function() {
                    that.cache.$to_raw_input.parent().hide();
                    that.cache.$from_raw_input.parent().addClass("shorter").next().addClass("visible");
                    $(".sources_toolbar").show();
                }, 10);
                break;
            case 'to':
                window.setTimeout(function() { // this is here to fix a bug where the caret is not displayed in the input field
                    that.cache.$from_raw_input.parent().hide();
                    that.cache.$to_raw_input.parent().addClass("shorter").next().addClass("visible");
                    $(".sources_toolbar").show();
                }, 10);
                break;
            default:
                $(".sources_toolbar").hide();
                this.current_flow_state = '';
                this.cache.$to_raw_input.parent().removeClass("shorter").show().next().removeClass("visible");
                this.cache.$from_raw_input.parent().removeClass("shorter").show().next().removeClass("visible");
        }
        return this;
    },
    showGlassPane:              function(options) {
        $(".glass_pane > #top").empty().addClass(options.style);
        $(".glass_pane > #bottom").empty().text(options.message);

        $(".glass_pane").addClass("show");
    },
    hideGlassPane:              function() {
        $(".glass_pane").removeClass("show");
    },
    showLocationError:          function() {
        var that = this,
            cancel_button = $("<button></button>").text("Cancel").click(function() {
                that.hideGlassPane();
            }),
            try_again_button = $("<button></button>").text("Try Again").click(function() {
                that.setLocationGPS(that.current_flow_state);
            }),
            buttons = $("<div class='buttons'></div>").append(cancel_button).append(try_again_button);

        $(".glass_pane > #top").text(that.config.messages.sorry_msg).removeClass("loading");
        $(".glass_pane > #bottom").text(that.config.messages.no_location_msg).append(buttons);
        this.ACCURACY_THRESHOLD = 1000;
    },
    locationSuccess:            function(position) {
        var that = this;
        if (position.coords.accuracy < that.ACCURACY_THRESHOLD ) {
            that.resolveLonLat(position.coords.longitude, position.coords.latitude, that.current_flow_state);
            that.map.setCenter(new telmap.maps.LatLng(position.coords.latitude, position.coords.longitude));
        } else {
            that.showLocationError();
        }
    },
//    locationError:              function(error) {
//        switch(error.code) {
//            case error.TIMEOUT:
//                alert ('Timeout');
//                break;
//            case error.POSITION_UNAVAILABLE:
//                alert ('Position unavailable');
//                break;
//            case error.PERMISSION_DENIED:
//                alert ('Permission denied');
//                break;
//            case error.UNKNOWN_ERROR:
//                alert ('Unknown error');
//                break;
//        }
//    },
    setLocationGPS:             function(address_type) {
        var that = this;
        if (!address_type) {
            address_type = 'from'
        }
        if (navigator.geolocation) {
            that.showGlassPane({style: "loading", message: that.config.messages.finding_location});
            navigator.geolocation.getCurrentPosition(function(p) {
                that.locationSuccess.call(that, p);
            }, function() {
                that.showLocationError.call(that);
            });
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
            from_x = $("#id_from_lon").val(),
            from_y = $("#id_from_lat").val(),
            to_x = $("#id_to_lon").val(),
            to_y = $("#id_to_lat").val(),
            from_city = $("#id_from_city").val(),
            to_city = $("#id_to_city").val();

        if (from_x && from_y && to_x && to_y) {
            $.ajax({
               url: that.config.estimation_service_url,
               type: 'get',
               dataType: 'json',
               data: { from_x: from_x, from_y: from_y, to_x: to_x, to_y: to_y,
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
                this.cache.$order_button.button("disable");
                if (this.map_markers[address.address_type]) {
                    this.map_markers[address.address_type].setMap();
                    delete this.map_markers[address.address_type];
                }
                this.renderMapMarkers();
                $("#ride_cost_estimate > .text").text(this.config.messages.estimation_msg);

                return;
            }
        }
        this.cache.$order_button.button("enable");
    },
    bookOrder:              function () {
        this.cache.$order_button.button("enable"); // otherwise the form would not submit
        this.cache.$order_button.click();
    }
});

