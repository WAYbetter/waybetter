//custom jQuery selector
jQuery.extend(jQuery.expr[':'], {
    focus: function(element) {
        return element == document.activeElement;
    }
});

// define a custom autocomplete widget
$.widget("custom.catcomplete", $.ui.autocomplete, {
    options: {
        minLength: 2,
        delay: 400
    },
    _response: function( content ) {
                if ( content.length && ! this.options.disabled && this.element.is(":focus")) {
                        content = this._normalize( content );
                        this._suggest( content );
                        this._trigger( "open" );
                } else {
                        this.close();
                }
                this.element.removeClass( "ui-autocomplete-loading" );
    },
    _renderMenu: function(ul, items) {
        var self = this,
                currentCategory = undefined,
                address_type = this.element[0].id.split("_")[1];

        ul.append("<li class='address-helper-autocomplete " + address_type + "'>" + OrderingHelper.config.autocomplete_msg + "</li>");
        $.each( items, function( index, item ) {
            self._renderItem( ul, item );
        });
    },
    _renderItem: function( ul, item) {
                return $( "<li></li>" )
                        .data( "item.autocomplete", item )
                        .append( "<a>" + item.label + "</a>" )
                        .addClass(item.category)
                        .appendTo( ul );
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
        resolve_address_url:        "", // '{% url cordering.passenger_controller.resolve_address %}'
        estimation_service_url:     "", // '{% url ordering.passenger_controller.estimate_ride_cost %}'
        resolve_coordinate_url:     "", // '{% url ordering.passenger_controller.resolve_coordinate %}'
        not_a_passenger_response:   "",
        not_a_user_response:        "",
        telmap_user:                "",
        telmap_password:            "",
        address_helper_msg_from:    "",
        address_helper_msg_to:      "",
        autocomplete_msg:           "",
        address_not_resolved_msg:   ""


    },
    ADDRESS_FIELD_ID_BY_TYPE:       {
        from:   "id_from_raw",
        to:     "id_to_raw"
    },
    map:                            {},
    map_markers:                    {},
    map_markers_popups:             {},
    _isEmpty:                   function(element) {
        var place_holder_text = $(element).attr("placeholder");

        return (! $(element).val() || $(element).val() == place_holder_text);    
    },
    _updateAddressControls:     function(element, address_type) {
        var address = Address.fromFields(address_type);
        var address_helper = $(element).siblings(".address-helper");
        if (address.isResolved()) {
            $(element).removeClass("not_resolved").removeClass("marker_disabled");
        } else {
            if (! this._isEmpty(element)) {
                $(element).addClass("not_resolved").removeClass("marker_disabled");
                address_helper.text(this.config.address_not_resolved_msg).addClass("address-error");
            } else {
                $(element).addClass("marker_disabled").removeClass("not_resolved");
                address_helper.text(this.config["address_helper_msg_" + address_type]).removeClass("address-error");
            }
        }
        
    },
    _onAddressInputBlur:        function(element, address_type) {
        this._updateAddressControls(element, address_type);
        var address = Address.fromFields(address_type);
        var address_helper = $(element).siblings(".address-helper");
         if (address.isResolved() || this._isEmpty(element)) {
            address_helper.fadeOut("fast");
        }
        
    },
    _onAddressInputFocus:       function(element, address_type) {
        this._updateAddressControls(element, address_type);
        var address = Address.fromFields(address_type);
        var address_helper = $(element).siblings(".address-helper");
        if (! address.isResolved()) {
            $(element).removeClass("not_resolved").addClass("marker_disabled");
            address_helper.text(this.config["address_helper_msg_" + address_type]).removeClass("address-error");
            address_helper.fadeIn("fast");
        }

    },
    init:                       function(config) {
        this.config = $.extend(true, {}, this.config, config);
        var that = this;        
        $("input:text").each(function(i, element) {
            var address_type = element.name.split("_")[0];
            var helper_div = $("<div class='address-helper round "+ address_type +"'></div>");
            $(element).after(helper_div);
            $(element).focus(function() {
                that._onAddressInputFocus(element, address_type);
            }).blur(function() {
                that._onAddressInputBlur(element, address_type);
            });
            $(element).catcomplete({
                cacheLength: 1,
                mustMatch: true,
                source: function (request, response) {
                    var params = { "term":request.term };  //TODO_WB: add max_size parameter, when "More..." is requested
                    $.ajax({
                        url: that.config.resolve_address_url,
                        data: params,
                        dataType: "json",
                        success: function(resolve_results) {
                            if (resolve_results.geocode.length == 0 && resolve_results.history.length == 0) {
                                response([]);

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
                        that._onAddressInputBlur(this, ui.item.address.address_type);
                    }

                },
                open: function(event, ui) {
                    $('ul.ui-autocomplete').css("z-index", 3000);
                }
            });
        });
        $("#id_from_raw, #id_to_raw").catcomplete("disable");

        $("input:button, #order_button").button();

        $("#order_button").button("disable");
        $("#id_from_raw, #id_to_raw").change(function() {
            that.validateForBooking();
        }).keydown(function(e) {
            // all other keys enable: tab, shift, ctrl, esc, left, right, enter
            var ignored_key_codes = [9, 13, 16, 17, 18, 20, 27, 37, 38, 39, 40, 91];
            if (ignored_key_codes.indexOf(e.keyCode) < 0) {
                $(this).catcomplete("enable");
            }
        });

        $("#order_form").submit(function() {
            if ($("#order_button").attr("disabled")) {
                return false;
            }

            $("#order_button").button("disable");

            $(this).ajaxSubmit({
                dataType: "json",
                complete: function() {
                    that.validateForBooking();
                },
                success: function(order_status) {
                    clearError();
                    if (order_status.status != "booked") {
                        Registrator.openErrorDialog(order_status.errors.title, order_status.errors.message);
                    } else {
                        Registrator.openRegistrationDialog(function() {
                            window.location.href = "/";
                        }, order_status.show_registration);
                    }
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    if (XMLHttpRequest.status == 403) {
                        if ( XMLHttpRequest.responseText == that.config.not_a_passenger_response ) {
                            Registrator.openPhoneDialog(that.bookOrder);
                        }
                    } else {
                        onError(XMLHttpRequest, textStatus, errorThrown);
                    }
                }
            });

            return false;
        }); // submit

        this.initMap();

        //TODO_WB:add a check for map, timeout and check again.
        setTimeout(that.initPoints, 100);
        setTimeout(function() {
            $("#id_from_raw, #id_to_raw").catcomplete("enable");
        }, 500);
        return this;
    }, // init
    initMap:                    function () {
        var prefs = {
            mapTypeId:telmap.maps.MapTypeId.ROADMAP,
            suit:telmap.maps.SuitType.MEDIUM_4,
            navigationControlOptions:{style:telmap.maps.NavigationControlStyle.ANDROID},
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
            icon_image = new telmap.maps.MarkerImage("/static/img/" + address.address_type + "_map_marker.png", undefined, undefined, {x:35, y:30}),
            point = new telmap.maps.Marker({
                map:        this.map,
                position:   new telmap.maps.LatLng(address.lat, address.lon),
                draggable:  true,
                icon:       icon_image,
                cursor:     'move',
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
            var info = new telmap.maps.InfoWindow({
                content: "<div style='font-family:Arial,sans-serif;font-size:0.8em;'>" + point.location_name + "<div>",
                disableAutoPan: true
            });

//            info.open(map, point);
            if (that.map_markers_popups[i]) {
                that.map_markers_popups[i].close();
            }
            that.map_markers_popups[i] = info;

        });
        if (that.map_markers.to && that.map_markers.from) {

            // make room for estimation box
            var delta = (bounds.ne.y - bounds.sw.y) * 0.5;
            var newPoint = new telmap.maps.LatLng(bounds.ne.y + delta, bounds.ne.x);
            bounds.extend(newPoint);

            map.fitBounds(bounds);
            map.panToBounds(bounds);

        } else {
            map.panTo(bounds.getCenter());
        }
    },
    updateAddressChoice:        function(address) {
        address.populateFields();
        this.addPoint(address);
        $("#id_from_raw, #id_to_raw").catcomplete("disable");
        if (address.address_type == "from") {
            $("#id_to_raw").focus();
        } else {
            $("#id_to_raw").blur();
        }

        this.getRideCostEstimate();
       this.validateForBooking();
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
        var label = data.label + " ";
        label += data.currency + data.estimated_cost;
        label += " (" + data.estimated_duration + ")";
        $("#ride_cost_estimate").html(label).show();
    },
    validateForBooking:         function() {
        for (var address_type in this.ADDRESS_FIELD_ID_BY_TYPE) {
            var address = Address.fromFields(address_type);
            if (!address.isResolved()) {
                $("#order_button").button("disable");
                if (this.map_markers[address.address_type]) {
                    this.map_markers[address.address_type].setMap();
                    delete this.map_markers[address.address_type];
                }
                this.renderMapMarkers();
                $("#ride_cost_estimate").empty().hide();
                return;
            }
        }
        $("#order_button").button("enable");
    },
    bookOrder:              function () {
        $("#order_button").button("enable"); // otherwise the form would not submit
        $("#order_form").submit();
    }
});

var SelectFromHistoryHelper = Object.create({
    config:     {
        fetch_address_url:  "",
        orders_index:       0

    },
    initialized:            false,
    init:       function($tabs, config) {
        $.extend(true, this.config, config);

        if ($tabs.tabs('option', 'selected') == this.config.orders_index) {
            this.from_selector = new HistorySelector($("#id_from_raw"));
            this.to_selector = new HistorySelector($("#id_to_raw"));
        }
        this.initialized = true;
    },
    updateGrid:   function() {
        if (this.initialized) {
            var selectors = [this.from_selector, this.to_selector];
            for (var i in selectors) {
                if (selectors[i].is_active) {
                    selectors[i].activate();
                }
            }
        }
    }
});

var HistorySelector = defineClass({
    name: "HistorySelector",
    construct:      function($input) {
        var that = this;
        this.$input = $input;
        this.select_button = $("<a>").attr("href", "#")
                                     .addClass("input_history_helper");
        this.$input.after(this.select_button);
        this.select_button.click(function() {
            that.activate();
            return false;
        });
    },
    methods: {
        fetchAddress:       function($td) {
            var that = this,
                order_id = $td.parent().attr("order_id"),
                address_type = $td.attr("field_type").toLowerCase();
            
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
            $("#tabs table td.order_history_column_From, #tabs table td.order_history_column_To")
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

var OrderHistoryHelper = Object.create({
    config:     {
        order_history_url:              "",
        page_label:                     "",
        of_label:                       "",
        order_history_columns:          [],
        order_history_column_names:     [],
        order_history_fields:           [],
        rating_choices:                 [],
        rating_disabled:                false
    },
    current_params:                     {},
    rating_initialized:                 false,
    init:           function(config) {
        var that = this;
        // merge the given config with current config
        $.extend(true, this.config, config);
        $("#search_button").click(function() {
            that.doSearch.call(that)
        });
        $("#reset_button").click(function() {
            if ($("#keywords").val()) {
                $("#keywords").val('');
                that.doSearch.call(that);
            }
        });
        $("#keywords").keypress(function(event) {
            if (event.keyCode == '13') { // enter
                that.doSearch.call(that);
            }
        });

        this.loadHistory({});
    },
    loadHistory:    function(params) {
        if (! this.config.order_history_url) {
            window.location = window.location; // reload page if not initialized
            return;
        }

        var that = this;
        $("#orders_history_grid table").animate({
            color: "#949494"
        }, 200);
        $("#orders_history_pager").append("<img src='/static/img/indicator_small.gif'/>");
        if (params.sort_by && this.current_params.sort_by &&
            params.sort_by == this.current_params.sort_by) {
                this.toggleSortDir();
        }
        $.extend(true, this.current_params, params);
        $.ajax({
            url:        this.config.order_history_url,
            type:       'get',
            data:       this.current_params,
            dataType:   'json',
            success:    function(json) {
                that.drawPager(json);
                that.drawTable(json.object_list, json.page_size);
                SelectFromHistoryHelper.updateGrid();
            },
            error:      function(xhr, textStatus, errorThrown) {
                alert('error loading history: ' + xhr.responseText);
            }
        });
    },
    drawPager:      function(data) {
        //Use: data["number"], data["has_other_pages"], data["start_index"], data["end_index"], data["has_next"], data["next_page_number"], ...
        var that = this,
            html = "";
        if (data.has_other_pages) {
            var $prev_button = $("<button class='wb_button gray'>").append("&lt;"),
                $next_button = $("<button class='wb_button gray'>").append(">"),
                $pager_text = $("<span>").append(that.config.page_label + " "
                        + data.number + " "
                        + that.config.of_label + " "
                        + data.num_pages + " ");

            if (data.has_previous) {
                $prev_button.attr("disable", "");
                $prev_button.click(function() {
                    that.loadHistory({
                        page:   data.previous_page_number
                    });
                });
            } else {
                $prev_button.attr("disable", "disable");
            }
            if (data.has_next) {
                $next_button.attr("disable", "");
                $next_button.click(function() {
                    that.loadHistory({
                        page:   data.next_page_number
                    });
                });
            } else {
                $next_button.attr("disable", "disable");
            }
        }
        $("#orders_history_pager").empty().append($prev_button, $pager_text, $next_button);
    },
    drawTable:      function(orders, page_size) {

        var that = this,
            baseBgColor = "style='background-color: lightGray'",
            $table = $("<table>");

        if ("keywords" in that.current_params && that.current_params.keywords != "") {
            $table.append($("<caption>").append("Results matching " + that.current_params.keywords));
        }
        var $header_row = $("<tr>");

        $.each(that.config.order_history_fields, function(i, val) {
            //var $th = $("<th>").append($('<a href="#" id="history_header_label_' + i + '">'));
            var link= $('<a>').attr( 'id', 'history_header_label_' + i  ).attr( 'href', '#'  ).append(that.config.order_history_column_names[i]).click(function() {
                        that.loadHistory({
                            sort_by: val
                        });
                    });
            // var $th = $("<th>").html('<a href="#" id="history_header_label_' + i + '">' + that.config.order_history_column_names[i] + '</a>')
            var $th = $("<th>").append(link);
            $header_row.append($th);
        });
        $table.append($header_row);
        var choices = this.config.rating_choices;
        $.each(orders, function(i, order) {
            var $tr = $("<tr>").attr("order_id", order.Id);
            if (i % 2 == 0) $tr.addClass('even_row');

            $.each(that.config.order_history_columns, function(name_index, val) {
                var $td;
                if (name_index == 4) {
                    // rating column
                    $rating_select = $("<select name='selrate'>");
                    for (var i = 0; i < choices.length; i++) {
                        $rating_select.append($("<option value='" + choices[i].val + "'>" + choices[i].name + "</option>"));
                    }

                    $wrapper = $("<div id='rating_wrapper_" + order["Id"] + "'>")
                                .addClass('stars-wrapper')
                                .attr("order_id", order["Id"])
                                .attr("rating", order["Passenger Rating"])
                                .append($rating_select);
                    $form = ($("<form>")).append($wrapper);
                    $td = $("<td>").append($form);
                }
                else {
                    $td = $("<td>").attr("field_type", val).addClass('order_history_column_' + val)
                        .append(order[that.config.order_history_columns[name_index]]);
                }
                $tr.append($td);
            });
            $table.append($tr);
        });
        $("#orders_history_grid").empty().append($table);
        $("#orders_history_grid table").animate({
            color: "black"
        }, 400);
        this.initRating();
    },
    doSearch:       function() {
        this.loadHistory({
            keywords: $("#keywords").val()
        });
    },
    toggleSortDir:  function() {
        if (this.current_params.sort_dir) {
            if (this.current_params.sort_dir == "")
                this.current_params.sort_dir = "-";
            else
                this.current_params.sort_dir = "";
        }
        else {
            this.current_params.sort_dir = "-";
        }
    },
    initRating:     function() {
        var widgets = {};
        var that = this;
        $(".stars-wrapper").each(function(index) {
                $(this).stars({
                    inputType: "select",
                    disabled: that.config.rating_disabled,
        //                captionEl: $("#stars-cap"),
                    callback: function(ui, type, value) {
                        var order_id = ui.element.attr("order_id");
                        $.ajax({
                            url: "/services/rate_order/" + order_id,
                            type: "POST",
                            data: { rating: value},
                            success: function() {
                                $("#stars-wrapper").stars("select", value);
                                $("#stars-wrapper-red").html(value == ui.options.cancelValue ? "Rating removed" : "Rating saved! (" + value + ")").stop().css("opacity", 1).fadeIn(30);
                                $("#stars-wrapper2-red").fadeOut(1000);
                            },
                            error: function(XMLHttpRequest, textStatus, errorThrown) {
                                alert(XMLHttpRequest.responseText);
                            }
                        });
                    }
                });
        });
        $(".stars-wrapper").each(function(index) {
            if ($(this).attr('rating') && $(this).attr('rating') != "null") {
                var rating = $(this).attr('rating');
                $(this).stars("select", rating);
            }
        });
        this.rating_initialized = true;
    }

});

