// define a custom autocomplete widget
$.widget("custom.catcomplete", $.ui.autocomplete, {
    options: {
        minLength: 2,
        delay: 400
    },
    // wrap jquery-ui's for removing additional classes  upon response
    responseWrapper: function() {
        this.response.apply( this, arguments );

        var input_type = OrderingHelper._getInputType(this.element),
            $header = $(".address-helper-autocomplete"),
            loader_class = "address-helper-loading-" + input_type;

        if (this.element.hasClass("ui-autocomplete-loading")){
            $header.addClass(loader_class);
        }
        else{
            $header.removeClass(loader_class);
            $(".address-helper").filter("." + input_type).removeClass(loader_class);
        }
    },
    _renderMenu: function(ul, items) {
        var self = this,
                currentCategory = undefined,
                input_type = OrderingHelper._getInputType(this.element);

        ul.append("<li class='address-helper-autocomplete " + input_type + "'>" + OrderingHelper.config.autocomplete_msg + "</li>");
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

// selectFirst for autocomplete-ui, modified for catcomplete
(function($) {
    $(".ui-autocomplete-input").live("catcompleteopen", function() {
        var autocomplete = $(this).data("catcomplete"),
                menu = autocomplete.menu;

        if (!autocomplete.options.selectFirst) {
            return;
        }

        menu.activate($.Event({ type: "mouseenter" }), menu.element.children().first().next());
    });

}(jQuery));

var OrderingHelper = Object.create({
    config:     {
        resolve_address_url:        "", // '{% url cordering.passenger_controller.resolve_address %}'
        estimation_service_url:     "", // '{% url ordering.passenger_controller.estimate_ride_cost %}'
        resolve_coordinate_url:     "", // '{% url ordering.passenger_controller.resolve_coordinate %}'
        not_a_user_response:        "",
        telmap_user:                "",
        telmap_password:            "",
        telmap_languages:           "",
        address_helper_msg_from:    "",
        address_helper_msg_to:      "",
        autocomplete_msg:           "",
        address_not_resolved_msg:   "",
        estimation_msg:             "",
        order_tracker_visible:      false,
        pickup_placeholder_text:     "",
        dropoff_placeholder_text:    "",
        hidden_fields:              [],
        update_address_callback:    undefined



    },
    map:                            {},
    map_markers:                    {},
    map_markers_popups:             {},
    map_was_reset:                  false,
    telmap_prefs:                   {},
    _isEmpty:                   function(element) {
        var place_holder_text = $(element).attr("placeholder");

        return (! $(element).val() || $(element).val() == place_holder_text);
    },
    _getInputType: function(input_element){
            return ($(input_element).hasClass("address_ac_from")) ? 'from' : ($(input_element).hasClass("address_ac_to")) ? 'to' : 'plain';
    },
    _updateAddressControls:     function(element, address_type) {
        var address = Address.fromFields(address_type);
        var address_helper = $(element).siblings(".address-helper");
        if (address.isResolved()) {
            $(element).removeClass("not_resolved").removeClass("marker_disabled");
        } else {
            if (! this._isEmpty(element)) {
                $(element).addClass("not_resolved").removeClass("marker_disabled");
                address_helper.text(this.config.address_not_resolved_msg).addClass("address-error").fadeIn("fast");
            } else {
                $(element).addClass("marker_disabled").removeClass("not_resolved");
                var input_type = this._getInputType(element);
                if (this.config["address_helper_msg_" + input_type]) {
                    address_helper.text(this.config["address_helper_msg_" + input_type]).removeClass("address-error");
                }
            }
        }

    },
    _onAddressInputBlur:        function(element, address_type) {
        this._updateAddressControls(element, address_type);
        var address = Address.fromFields(address_type);
        var address_helper = $(element).siblings(".address-helper");
        var input_type = this._getInputType(element);

        address_helper.removeClass("address-helper-loading-" + input_type);
        if (address.isResolved() || this._isEmpty(element)) {
             address_helper.fadeOut("fast");
         }
    },
    _onAddressInputFocus:       function(element, address_type) {
        this._updateAddressControls(element, address_type);
        var address = Address.fromFields(address_type);
        var address_helper = $(element).siblings(".address-helper");
        if (! address.isResolved()) {
            // TODO_WB: there is bug when logged in as a business, it might be related to the history columns
            $(element).catcomplete("search");
            $(element).removeClass("not_resolved").addClass("marker_disabled");

            var input_type = this._getInputType(element);
            if (this.config["address_helper_msg_" + input_type]) {
                address_helper.text(this.config["address_helper_msg_" + input_type]).removeClass("address-error");
            }
            address_helper.fadeIn("fast");
        }
    },

    _makeAddressInput:          function(element, onSelect){
        var that = this;

        var address = Address.fromInput(element);
        var address_type = address.address_type;

        var input_type = this._getInputType(element);

        var helper_div = $("<div class='address-helper round " + input_type + "'></div>");
        $(element).after(helper_div);
        $(element).focus(
            function() {
                that._onAddressInputFocus(element, address_type);
            }).blur(function() {
                that._onAddressInputBlur(element, address_type);
            });
        $(element).catcomplete({
            mustMatch: true,
            selectFirst: true,
            source: function (request, response) {
                var catcomplete_instance = this;

                $(".address-helper, .address-helper-autocomplete").filter("." + input_type).addClass("address-helper-loading-" + input_type);
                var address = undefined,
                    lat = undefined,
                    lon = undefined;

                address = (input_type == 'from') ? Address.fromFields('to') : Address.fromFields('from');
                if (address.isResolved()) {
                    lat = address.lat;
                    lon = address.lon;
                }
                //TODO_WB: add max_size parameter, when "More..." is requested
                $.ajax({
                    url: that.config.resolve_address_url,
                    data: { "term":request.term, "lon": lon, "lat": lat },
                    dataType: "json",
                    success: function(resolve_results) {
                        if (resolve_results.geocode.length == 0 && resolve_results.history.length == 0) {
                            catcomplete_instance.responseWrapper([]);

                        } else { // create autocomplete items from server response
                            var items = $.map(resolve_results.history, function(item) {
                                return {
                                    label: item.name,
                                    value: item.name,
                                    category: resolve_results.history_label,
                                    address: Address.fromServerResponse(item, address_type)
                                }
                            });

                            catcomplete_instance.responseWrapper(items.concat($.map(resolve_results.geocode, function(item) {
                                return {
                                    label: item.name,
                                    value: item.name,
                                    category: resolve_results.geocode_label,
                                    address: Address.fromServerResponse(item, address_type)
                                }
                            })));
                        }
                    },
                    error: function() {
                        catcomplete_instance.responseWrapper([]);
                    }
                });
            },
            select: onSelect || function (event, ui) {
                if (ui.item.address) {
                    that.updateAddressChoice(ui.item.address);
                    that._onAddressInputBlur(this, ui.item.address.address_type);
                }

            },
            open: function(event, ui) {
                $('ul.ui-autocomplete').css("z-index", 3000);
            }
        });
    },

    init:                       function(config) {
        var that = this;
        this.config = $.extend(true, {}, this.config, config);
        this.telmap_prefs = {
            mapTypeId:telmap.maps.MapTypeId.ROADMAP,
            suit:telmap.maps.SuitType.MEDIUM_4,
            navigationControlOptions:{style:telmap.maps.NavigationControlStyle.ANDROID},
            zoom:15,
            center:new telmap.maps.LatLng(32.09279909028302, 34.781051985221),
            login:{
                contextUrl: 'api.telmap.com/telmapnav',
                userName:   this.config.telmap_user,
                password:   this.config.telmap_password,
                languages:  [this.config.telmap_languages, this.config.telmap_languages],
                appName:    'wayBetter',
                callback:   function () {
                    that.resetMap.call(that);
                }
            }
        };
        $("#ride_cost_estimate").html(this.config.estimation_msg);

        $(".address_ac_from, .address_ac_to").each(function(i, element) {
            that._makeAddressInput(element);
        });

        $(".address_ac_from, .address_ac_to").catcomplete("disable");

        $("input:button, #order_button").button();

        $("#order_button").button("disable");

        // prevent input fields and submit button from ordering on 'enter'
        $("#order_form input[type!='hidden']").add("#order_form button[type='submit']").keydown(function(e) {
            if (e.keyCode == 13){
                e.preventDefault();
            }
        });

        var onentry_val = "";
        $(".address_ac_from, .address_ac_to").live('change', function() {
            that.validateForBooking();
        }).live('keydown', function(e) {
            onentry_val = $(this).val();
            // all other keys enable: tab, shift, ctrl, esc, left, right, enter
            var ignored_key_codes = [9, 13, 16, 17, 18, 20, 27, 37, 38, 39, 40, 91];
            if (ignored_key_codes.indexOf(e.keyCode) < 0) {
                $(this).catcomplete("enable");
            }
        }).live('keyup', function(){
            if ($(this).val() != onentry_val){
                var address = Address.fromInput(this);
                that._onAddressInputFocus($(this), address.address_type);
                that.validateForBooking();
            }
        });

        this.initMap();

        //TODO_WB:add a check for map, timeout and check again.
        setTimeout(that.initPoints, 100);
        setTimeout(function() {
            $(".address_ac_from, .address_ac_to").catcomplete("enable");
        }, 500);
        return this;
    }, // init
    initMap:                    function () {
        this.map = new telmap.maps.Map(document.getElementById("map"), this.telmap_prefs);
        window.onresize = function(){ telmap.maps.event.trigger(this.map, "resize"); };
    },
    resetMap:                 function (e, a) {
        var that = this;
        if (! this.map_was_reset) {
            this.map_was_reset = true;
            this.map.logout(function(e, a) {
                    that.map.login(that.telmap_prefs.login);
                });
        }
    },
    initPoints:                 function () {
        var that = this;
        $(".address_ac_from, .address_ac_to").each(function(i, input_element) {
            var address = Address.fromInput(input_element);
            if (address.lon && address.lat) {
                that.removePoint(address.address_type);
                that.addPoint(address);
            }
        });
    },
    removePoint:                function(address_type){
        if (this.map_markers[address_type]) {
            this.map_markers[address_type].setMap(); // remove old marker from map
        }
    },
    addPoint:                   function (address) {
        var that = this,
            location_name = address.address_type + ": <br/>" + address.raw,
            input_type = this._getInputType($("#id_" + address.address_type + "_raw")),
            icon_image = new telmap.maps.MarkerImage("/static/images/" + input_type + "_map_marker.png", undefined, undefined, {x:35, y:30}),
            point = new telmap.maps.Marker({
                map:        this.map,
                position:   new telmap.maps.LatLng(address.lat, address.lon),
                draggable:  true,
                icon:       icon_image,
                cursor:     'move',
                title:      address.raw
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
        this.removePoint(address.address_type);
        this.map_markers[address.address_type] = point;
        this.renderMapMarkers();
    },
    renderMapMarkers:           function () {
        var that = this,
            map = this.map,
            markers = 0,
            bounds = new telmap.maps.LatLngBounds();

        $.each(this.map_markers, function (i, point) {
            markers++;
            bounds.extend(point.getPosition());
            var info = new telmap.maps.InfoWindow({
                content: "<div style='font-family:Arial,sans-serif;font-size:0.8em;'>" + point.location_name + "<div>",
                disableAutoPan: true
            });

            if (that.map_markers_popups[i]) {
                that.map_markers_popups[i].close();
            }
            that.map_markers_popups[i] = info;

        });
        if (markers > 1) {

            // make room for estimation box
            var delta = (bounds.ne.y - bounds.sw.y) * 0.5;
            var newPoint = new telmap.maps.LatLng(bounds.ne.y + delta, bounds.ne.x);
            bounds.extend(newPoint);

            map.fitBounds(bounds);
            map.panToBounds(bounds);

        } else if (bounds.valid) {
            map.panTo(bounds.getCenter());
        }
    },
    updateAddressChoice:        function(address) {
        address.populateFields();
        this.addPoint(address);
        $(".address_ac_from, .address_ac_to").catcomplete("disable").blur();
        $(".address_ac_to:blank").first().focus();

        this.getRideCostEstimate();
        this.validateForBooking();

        if (this.config.update_address_callback){
            this.config.update_address_callback.call(this, address);
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
        if (data.estimated_cost && data.estimated_duration){
            var label = data.label + " ";
            label += data.currency + data.estimated_cost;
            label += " (" + data.estimated_duration + ")";
        }
        else{
            var label = data.label;
        }
        $("#ride_cost_estimate").html(label).show();
    },
    validateForBooking:         function() {
        var that = this;
        var enable_button = true;
        $(".address_ac_from, .address_ac_to").each(function(i, input_element) {
            var address = Address.fromInput(input_element);
            var input_type = that._getInputType(input_element);

            if (!address.isResolved()) {
                address.clearFields();
                if (that.map_markers[address.address_type]) {
                    that.map_markers[address.address_type].setMap();
                    delete that.map_markers[address.address_type];
                }
                that.renderMapMarkers();
                $("#ride_cost_estimate").html(that.config.estimation_msg);
                if (input_type == 'from') {
                    $("#order_button").button("disable"); // disable ordering if from is not resolved
                    enable_button = false;
                }
            }
        });
        if (enable_button) {
            $("#order_button").button("enable"); // enable ordering
        }
    },
    bookOrder:              function () {
        $("#order_button").button("enable"); // otherwise the form would not submit
        $("#order_form").submit();
    },

    createHiddenFields: function(address_type) {
        $.each(this.config.hidden_fields, function(i, field_name) {
            var $field = $('<input type="hidden" id="id_' + address_type + '_' + field_name + '" name="' + address_type + '_' + field_name + '"/>');
            $("#order_form").append($field);
        });
        $("#order_form").append($('<input type="hidden" id="id_geocoded_' + address_type + '_raw" name="geocoded_' + address_type + '_raw"/>'));
    },

    deleteHiddenFields: function(address_type) {
        $("[name^=" + address_type + "]").remove();
        $("#id_geocoded_" + address_type + "_raw").remove();
    },

    asPickup: function(locator) {
        $(locator + " input").removeClass("b_marker address_ac_to").addClass("a_marker address_ac_from").attr("placeholder", this.config.pickup_placeholder_text);
        $(locator + " .address-helper").removeClass("to address-helper-loading-to").addClass("from");
    },

    asDropoff: function(locator) {
        $(locator + " input").removeClass("a_marker address_ac_from").addClass("b_marker address_ac_to").attr("placeholder", this.config.dropoff_placeholder_text);
        $(locator + " .address-helper").removeClass("from address-helper-loading-from").addClass("to");
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
        this.$tabs = $tabs;
        if ($tabs.tabs('option', 'selected') == this.config.orders_index) {
            this.from_selector = new HistorySelector($("#id_from_raw"));
            this.to_selector = new HistorySelector($("#id_to_raw"));
        }
        this.initialized = true;
    },
    selectHistoryTab:   function() {
        this.$tabs.tabs('option', 'selected', this.config.orders_index);
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
        var that = this,
            address = Address.fromInput($input);
        this.$input = $input;
        this.input_type = address.address_type;

        this.$input.focus(function() {
            that.activate();
        });
        this.$input.blur(function() {
            that.deactivate();
        });
    },
    methods: {
        fetchAddress:       function($td) {
            var that = this,
                order_id = $td.parent().attr("order_id"),
                address_type = $td.attr("field_type").toLowerCase();
            
            $.getJSON(SelectFromHistoryHelper.config.fetch_address_url, {order_id: order_id, address_type: address_type}, function(response) {
                var address = Address.fromServerResponse(response, that.input_type);
                OrderingHelper.updateAddressChoice(address);

            });
        },
        activate:           function() {
            var that = this;

            SelectFromHistoryHelper.selectHistoryTab();

            SelectFromHistoryHelper.to_selector.deactivate();
            SelectFromHistoryHelper.from_selector.deactivate();

            $("#tabs table td.order_history_column_From, #tabs table td.order_history_column_To").not(":empty")
                    .addClass("select-address")
                    .addClass(that.input_type)
                    .effect("highlight", {color: 'white'}, 600)
                    .mousedown(function () {
                        that.fetchAddress($(this));
                        that.deactivate();
                    });

            this.is_active = true;
            
        },
        deactivate:         function() {
            var that = this;
            this.is_active = false;
            $("#tabs table td.select-address").unbind("mousedown").removeClass("select-address").removeClass(that.input_type);

        }

    }
});

var OrderHistoryHelper = Object.create({
    config:     {
        id_history_grid:                "",
        id_history_pager:               "",
        order_history_url:              "",
        page_label:                     "",
        of_label:                       "",
        order_history_columns:          [],
        order_history_column_names:     [],
        order_history_fields:           [],
        rating_choices:                 [],
        rating_disabled:                false,
        sorting_disabled:               false,
        load_history_on_init:           true,
        load_history_callback:          undefined
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

        if (this.config.load_history_on_init){
            this.loadHistory({});
        }
    },
    loadHistory:    function(params) {
        if (! this.config.order_history_url) {
            window.location = window.location; // reload page if not initialized
            return;
        }

        var that = this;
        $("#" + that.config.id_history_grid + " table").animate({
            color: "#949494"
        }, 200);
        $("#" + that.config.id_history_pager).append("<img src='/static/images/indicator_small.gif'/>");
        if (params.sort_by && this.current_params.sort_by &&
            params.sort_by == this.current_params.sort_by) {
                this.toggleSortDir();
        }

        $.extend(true, this.current_params, params);
        this.current_params.status_list = params.status_list; // don't extend the status list

        $.ajax({
            url:        this.config.order_history_url,
            data:       this.current_params,
            dataType:   'json',
            success:    function(json) {
                that.current_params.sort_dir = json.sort_dir;
                that.current_params.sort_by = json.sort_by;

                that.drawPager(json);
                that.drawTable(json.object_list, json.page_size);
                SelectFromHistoryHelper.updateGrid();
                if (that.config.load_history_callback){
                    that.config.load_history_callback.call();
                }
            },
            error:      function(xhr, textStatus, errorThrown) {
                return false;
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
                    that.loadHistory($.extend(true, that.current_params, {page:   data.previous_page_number}));
                });
            } else {
                $prev_button.attr("disable", "disable");
            }
            if (data.has_next) {
                $next_button.attr("disable", "");
                $next_button.click(function() {
                    that.loadHistory($.extend(true, that.current_params, {page:   data.next_page_number}));
                });
            } else {
                $next_button.attr("disable", "disable");
            }
        }
        $("#" + that.config.id_history_pager).empty().append($prev_button, $pager_text, $next_button);
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
            if (that.config.order_history_column_names[i] == "_HIDDEN"){
                return true; // don't render hidden columns
            }

            //var $th = $("<th>").append($('<a href="#" id="history_header_label_' + i + '">'));
            var link= $('<a>').attr( 'id', 'history_header_label_' + i  ).append(that.config.order_history_column_names[i]);
            if (! that.config.sorting_disabled) {
                link.attr( 'href', '#'  ).click(function() {
                    that.loadHistory({
                        sort_by: val
                    });
                });
            }
            // var $th = $("<th>").html('<a href="#" id="history_header_label_' + i + '">' + that.config.order_history_column_names[i] + '</a>')
            var $th = $("<th>").append(link);
            $header_row.append($th);
        });
        $table.append($header_row);
        var choices = this.config.rating_choices;
        $.each(orders, function(i, order) {
            var $tr = $("<tr>").attr("order_id", order.Id);
            if (order.status){
                $tr.data("status", order.status);
            }
            if (i % 2 == 0) $tr.addClass('even_row');

            $.each(that.config.order_history_columns, function(name_index, val) {
                if (val == "status"){
                    return true; // don't render the status column
                }
                var $td;
                if (val == "Passenger Rating") {
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
        $("#" + that.config.id_history_grid).empty().append($table);
        $("#" + that.config.id_history_grid + " table").animate({
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
                            url: "/services/rate_order/" + order_id + "/",
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

