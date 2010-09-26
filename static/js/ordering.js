// define a custom autocomplete widget
$.widget("custom.catcomplete", $.ui.autocomplete, {
    options: {
        minLength: 2,
        delay: 400
    },
    _renderMenu: function(ul, items) {
        var self = this,
                currentCategory = undefined;

        $.each(items, function(index, item) {
            if (item.category != currentCategory) {
                ul.append("<li class='ui-autocomplete-category'>" + item.category + "</li>");
                currentCategory = item.category;
            }
            self._renderItem(ul, item);
        });
    }
});

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
        unresolved_label:           "", // "{% trans 'Could not resolve address' %}"
        resolve_address_url:        "", // '{% url cordering.passenger_controller.resolve_address %}'
        estimation_service_url:     "", // '{% url ordering.passenger_controller.estimate_ride_cost %}'
        not_a_passenger_response:   "",
        not_a_user_response:        ""

    },
    ADDRESS_FIELD_ID_BY_TYPE:       {
        from:   "id_from_raw",
        to:     "id_to_raw"
    },
    map_markers:                    {},
    map_markers_popups:             {},
    init:                       function(config) {
        this.config = $.extend(true, {}, this.config, config);
        var that = this;        
        $("input:text").each(function(i, element) {
            var address_type = element.name.split("_")[0];
            $(element).catcomplete({
                source: function (request, response) {
                    var params = { "term":request.term };  //TODO_WB: add max_size parameter, when "More..." is requested
                    $.ajax({
                        url: that.config.resolve_address_url,
                        data: params,
                        dataType: "json",
                        success: function(resolve_results) {
                            if (resolve_results.geocode.length == 0 && resolve_results.history.length == 0) {
                                response([
                                    {
                                        label: that.config.unresolved_label,
                                        value: request.term
                                    }
                                ]);

                            } else { // create autocomplete items from server response
                                var items = $.map(resolve_results.history, function(item) {
                                    return {
                                        label: item.name,
                                        value: item.name,
                                        category: resolve_results.history_label,
                                        address: Address.fromServerResponse(item, address_type)
                                    }
                                });

                                response(items.concat($.map(resolve_results.geocode, function(item) {
                                    return {
                                        label: item.name,
                                        value: item.name,
                                        category: resolve_results.geocode_label,
                                        address: Address.fromServerResponse(item, address_type)
                                    }
                                })));
                            }
                        }
                    });
                },
                select: function (event, ui) {
                    if (ui.item.address) {
                        that.updateAddressChoice(ui.item.address);
                    }
                },
                open: function(event, ui) {
                    $('ul.ui-autocomplete').css("z-index", 3000);
                }
            });
        });

        $("input:button, input:submit").button();

        $("#order_button").button("disable");
        $("#id_from_raw, #id_to_raw").change(function() {
            that.validateForBooking();
        });

        $("#order_form").submit(function() {
            if ($("#order_button").attr("disabled")) {
                return false;
            }

            $("#order_button").button("disable");

            $(this).ajaxSubmit({
                dataType: "json",
                success: function(order_status) {
                    clearError();
                    if (order_status.status == "booked") {
                        window.location.href = order_status.order_status_url;
                    } else {
                        alert("error: " + order_status.errors);
                    }
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    if (XMLHttpRequest.status == 403) {
                        if (XMLHttpRequest.responseText == that.config.not_a_user_response) {
                            Registrator.openRegistrationDialog(that.bookOrder);
                        } else if (XMLHttpRequest.responseText == that.config.not_a_passenger_response) {
                            Registrator.openPhoneDialog(that.bookOrder);
                        }
                    } else {
                        onError(XMLHttpRequest, textStatus, errorThrown);
                    }
                }
            });

            return false;
        }); // submit

        //TODO_WB:add a check for map, timeout and check again.
        setTimeout(that.initPoints, 100);

        return this;
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
        var location_name = address.address_type + ": " +
                $('#id_' + address.address_type + '_raw').val();

        var icon_image = "/static/img/" + address.address_type + "_map_marker.png";

        //TODO_WB:fix center behavior to show both points
        var center = true;
        var point = new MapMarker(address.lon, address.lat, location_name, icon_image, center);
        this.map_markers[address.address_type] = point;
        this.renderMapMarkers();
    },
    renderMapMarkers:           function () {
        var map = g_waze_map.map;
        var markers = map.getLayersByName("Markers")[0];
        if (!markers) {
            markers = new OpenLayers.Layer.Markers("Markers");
            map.addLayer(markers);
        }
        markers.clearMarkers();
        var bounds = new OpenLayers.Bounds();
        for (var location_name in this.map_markers) {
            var point = this.map_markers[location_name];
            var lonlat = new OpenLayers.LonLat(point.lon, point.lat);
            bounds.extend(lonlat);

            var size = new OpenLayers.Size(15, 34);
            var offset = new OpenLayers.Pixel(-(size.w / 2), -size.h);
            var icon = new OpenLayers.Icon(point.icon_image, size, offset);
            markers.addMarker(new OpenLayers.Marker(lonlat, icon));
            if (this.map_markers_popups[location_name]) {
                map.removePopup(this.map_markers_popups[location_name]);
            }
            this.map_markers_popups[location_name] =
                    new OpenLayers.Popup.FramedCloud("test", lonlat, null,
                    "<div style='font-family:Arial,sans-serif;font-size:0.8em;'>" + point.location_name + "<div>",
                    anchor = null, true, null);
            map.addPopup(this.map_markers_popups[location_name]);
        }
        map.zoomToExtent(bounds);
    },
    updateAddressChoice:        function(address) {
        address.populateFields();
        this.addPoint(address);
        if (address.address_type == "from") {
            $("#id_to_raw").focus();
        }
        this.getRideCostEstimate();
        this.validateForBooking();
    },
    getRideCostEstimate:        function() {
        var that = this,
            from_x = $("#id_from_lon").val(),
            from_y = $("#id_from_lat").val(),
            to_x = $("#id_to_lon").val(),
            to_y = $("#id_to_lat").val();

        if (from_x && from_y && to_x && to_y) {
            $.ajax({
               url: that.config.estimation_service_url,
               type: 'get',
               dataType: 'json',
               data: { from_x: from_x, from_y: from_y, to_x: to_x, to_y: to_y},
               success: that.renderRideEstimatedCost
            });
        }
    },
    renderRideEstimatedCost:    function (data) {
        var label = "<img src='/static/img/cost.jpg'>" + data.label + ":";
        label += data.estimated_cost + data.currency;
        label += " (" + data.estimated_duration + ")";
        $("#ride_cost_estimate").html(label);
    },
    validateForBooking:         function() {
        for (var address_type in this.ADDRESS_FIELD_ID_BY_TYPE) {
            var address = Address.fromFields(address_type);
            if (!address.isResolved()) {
                $("#order_button").button("disable");
                delete this.map_markers[address.address_type];
                this.renderMapMarkers();
                $("#ride_cost_estimate").empty();
                return;
            }
        }
        $("#order_button").button("enable");
    },
    bookOrder:              function () {
        $("#order_form").submit();
    }
});

var SelectFromHistoryHelper = Object.create({
    config:     {
        fetch_address_url:  "",
        orders_index:       0

    },
    init:       function($tabs, config) {
        this.config = $.extend(true, {}, this.config, config);

        if ($tabs.tabs('option', 'selected') == this.config.orders_index) {
            this.from_selector = new HistorySelector($("#id_from_raw"));
            this.to_selector = new HistorySelector($("#id_to_raw"));
        }
    },
    updateGrid:   function() {
        var selectors = [this.from_selector, this.to_selector];
        for (var i in selectors) {
            if (selectors[i].is_active) {
                selectors[i].activate();
            }
        }
    }
});

var HistorySelector = defineClass({
    name: "HistorySelector",
    construct:      function($input) {
        var that = this;
        this.$input = $input;
        this.select_button = $("<input>").attr("type", "button")
                                         .val("Select")
                                         .button();
        this.$input.after(this.select_button);
        this.select_button.click(function() {
            that.activate();
        });
    },
    methods: {
        fetchAddress:       function($td) {
            var that = this;

            var order_id = $($td.parent().children()[0]).text();
            var address_type = $td.attr("aria-describedby").split("_").pop().toLowerCase();
            $.getJSON(SelectFromHistoryHelper.config.fetch_address_url, {order_id: order_id, address_type: address_type}, function(response) {
                var address = Address.fromServerResponse(response, that.$input[0].id.split("_")[1]);
                OrderingHelper.updateAddressChoice(address);

            });
        },
        activate:           function() {
            var that = this;

            SelectFromHistoryHelper.to_selector.deactivate();
            SelectFromHistoryHelper.from_selector.deactivate();

            this.select_button.val("Cancel");
            this.select_button.unbind("click").click(function() {
                that.deactivate();
            });

            this.$input.addClass("select-address");
            $("#tabs table td[aria-describedby=orders_history_grid_From], #tabs table td[aria-describedby=orders_history_grid_To]")
                    .addClass("select-address")
                    .click(function () {
                        that.fetchAddress($(this));
                        that.deactivate();
                    });

            this.is_active = true;
            
        },
        deactivate:         function() {
            var that = this;
            this.is_active = false;
            this.select_button.val("Select");
            this.select_button.unbind("click").click(function() {
                that.activate();
            });
            
            this.$input.removeClass("select-address");
            $("#tabs table td.select-address").unbind("click").removeClass("select-address");

        }

    }
});




