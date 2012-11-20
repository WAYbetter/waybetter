var GoogleGeocodingHelper = Object.create({
    _geocoder: undefined,
    _directionsService: undefined,
    _pendingReverseGeocodeCallback: undefined,
    getGeocoder: function() {
        if (! this._geocoder) {
            this._geocoder =  new google.maps.Geocoder();
        }
        return this._geocoder;
    },
    getDirectionsService:function () {
        if (!this._directionsService) {
            this._directionsService = new google.maps.DirectionsService();
        }
        return this._directionsService;
    },
    getDirections: function(from_lat, from_lon, to_lat, to_lon, callback) {
        var that = this;
        var request = {
            origin: new google.maps.LatLng(from_lat, from_lon),
            destination: new google.maps.LatLng(to_lat, to_lon),
            travelMode: google.maps.TravelMode.DRIVING
        };
        that.getDirectionsService().route(request, callback);
    },
    geocode: function(address, callback, callback_arg) {
        this.getGeocoder().geocode({"address":address}, function (results, status) {
            callback(results, status, callback_arg);
        });
    },
    reverseGeocode:function (lat, lon, callback) {
        var lat_lon = new google.maps.LatLng(lat, lon);
        this.getGeocoder().geocode({'latLng':lat_lon}, function (results, status) {
            callback(results, status);
        });
    },
    reverseGeocodeToPickupAddress: function(lat, lon, id_textinput, callback) {
        var that = this;
        that._pendingReverseGeocodeCallback = callback;
        $.mobile.showPageLoadingMsg();
        that.reverseGeocode(lat, lon, function(results, status) {
            var res = null;
            if (status == google.maps.GeocoderStatus.OK && results.length) {
                res = that._checkValidPickupAddress(results[0], id_textinput);
//                that._pendingReverseGeocodeCallback = undefined;
            }

            $.mobile.hidePageLoadingMsg();
            if (res) {
                if (res.valid) {
                    callback(res.address);
                }
            } else {
                callback(null, lat, lon);
            }

        });
    },
    newPlacesAutocomplete: function (options) {
        options = $.extend(true, {
            id_textinput: "",
            beforePlaceChange: function(){},
            onValidAddress: function(address){},
            onMissingStreetNumber: function(){},
            onNoValidPlace: function(){}
        }, options);

        var autocomplete = new google.maps.places.Autocomplete(document.getElementById(options.id_textinput),
            {
                bounds: options.bounds || undefined,
                types: options.types || []
            });

        if (options.map){
            autocomplete.bindTo('bounds', options.map);
        }

        var that = this;
        google.maps.event.addListener(autocomplete, 'place_changed', function () {
            var place = this.getPlace();
            options.beforePlaceChange();
            that._onNewPlace.call(that, place, options);
        });

        return autocomplete;
    },
    showAutocomplete: function(){
        $(".pac-container").css("visibility", "visible");
    },
    hideAutocomplete: function(){
        $(".pac-container").css("visibility", "hidden");
    },
    _onNewPlace:function (place, options) {
        var result = this._checkValidPickupAddress(place, options.id_textinput);

        if (result.valid) {
            options.onValidAddress(result.address);
        }
        else if (result.missing_hn) {
            options.onMissingStreetNumber(result);
        }
        else if (place.geometry && place.geometry.location) {
            // try to get a valid point by reverse geocoding
            this.reverseGeocode(place.geometry.location.lat(), place.geometry.location.lng(), function (results, status) {
                var rev_result;
                if (status == google.maps.GeocoderStatus.OK && results.length) {
                    log("reverse geocode results:", results, "for place:", place);
                    rev_result = GoogleGeocodingHelper._checkValidPickupAddress(results[0], options.id_textinput);
                    rev_result.address.city = result.address.city;
                    if (result.address.description) { // add establishment description to returned address
                        rev_result.address.description = result.address.description;
                    }
                } else {
                    log("Geocoder failed due to: " + status);
                }

                if (rev_result && rev_result.valid) {
                    $("#" + options.id_textinput).val(results[0].formatted_address); // let the user see what we are validating
                    options.onValidAddress(rev_result.address);
                }
                else if (rev_result && rev_result.missing_hn) {
                    $("#" + options.id_textinput).val(results[0].formatted_address); // let the user see what we are validating
                    options.onMissingStreetNumber(rev_result);
                }

                else {
                    options.onNoValidPlace();
                }
            });
        }
        else {
            options.onNoValidPlace();
        }
    },
    _checkValidPickupAddress: function(place, id_textinput){
        var result = {
            valid: false,
            missing_hn: false,
            address: undefined
        };

        $.each(place.types || [], function (i, type) {
            if (type == "street_address") result.valid = true; // a "street_address" is exempt from checking procedure
            if (type == "route") result.missing_hn = true; // a "route" is assumed to be missing a house number
        });

        if (!result.valid) {
            // check address components for a valid street + house number address
            var street_number_component = this._getAddressComponent(place, "street_number"),
                route_component = this._getAddressComponent(place, "route");

            if (route_component && street_number_component) {
                var user_input = $("#" + id_textinput).val();

                // avoid cases where Google returns a house number although the user entered only a street name
                if (user_input.startsWith(route_component.short_name) && user_input.search(street_number_component.short_name) < 0) {
                    result.missing_hn = true;
                    log("google generated house number");
                } else {
                    result.valid = true;
                    log("valid pickup address");
                }
            }
        }

        result.address = this._addressFromPlace(place);

        // amir: guy - do we need this code? doesn't addressFromPlace calls normalizePlace that handles range of house numbers?
        if ( !result.address.house_number || (result.address.house_number.indexOf && result.address.house_number.indexOf("-") > -1)) {
            // this is a range of houses, a reverse geocode is underway...
            result.valid = false;
        }

        return result;
    },
    _addressFromPlace: function(place){
        place = this._normalizePlace(place);

        // address fields
        var street_address, house_number, city, name, lat, lon, description;

        var address_components = place.address_components || [];
        $.each(address_components, function (i, component) {
            var type = component.types[0];
            if (type == 'locality')
                city = component.long_name;
            else if (type == "route")
                street_address = component.long_name;
            else if (type == 'street_number')
                house_number = component.short_name; // normalized field
        });

        if (place.geometry && place.geometry.location){
            lat = place.geometry.location.lat();
            lon = place.geometry.location.lng();
        }

        if (street_address && house_number && city){
            name = street_address + " " + house_number + ", " + city;
        }
        else if (place.formatted_address){
            name = place.formatted_address;
        }

        // add description field for POI
        var poi_types = ["establishment", "train_station", "transit_station"];
        $.each(place.types || [], function (i, type) {
            if ($.inArray(type, poi_types) > -1){
                description = place.name;
                log("POI", type, description);
            }
        });

        return {
            city:city,
            street_address:street_address,
            house_number:house_number,
            description: description,
            name:name,
            lat:lat,
            lon:lon
        };
    },
    _normalizePlace: function(place){
        var that = this;
//        try {
            // fix interpolated street number component
            if (place.geometry.location_type == google.maps.GeocoderLocationType.RANGE_INTERPOLATED) {
                var component = that._getAddressComponent(place, 'street_number');
                if (component) {
                    // get the lower street number of the range
                    var range = component.long_name.split("-");
                    if (range.length == 2) {
                        var low = parseInt(range[0]);
                        var high = parseInt(range[1]);
                        if (that._pendingReverseGeocodeCallback) {
                            range = [];
                            for (var i = low; i <= high; i += 2) { range.push(i) }
                            var original_location = place.geometry.location;
                            var addresses = [];
                            var returned_geocode_calls = 0;
                            for (var j = 0; j < range.length; j++) {
                                var address = [that._getAddressComponent(place, 'route').long_name + " " + range[j],
                                    that._getAddressComponent(place, 'locality').long_name ].join(", ");

                                addresses.push({name: address, city: that._getAddressComponent(place, 'locality').long_name, callback_index: j});

                                that.geocode(address, function(result, status, original_address) {
                                    if (! that._pendingReverseGeocodeCallback) return;

                                    log("geocode for house range returned", result, status);
                                    returned_geocode_calls++;
                                    if (result) {
                                        original_address.lat = result[0].geometry.location.lat();
                                        original_address.lon = result[0].geometry.location.lng();
                                    } else {
                                        original_address.lat = 0
                                        original_address.lon = 0;
                                    }

                                    if (returned_geocode_calls == range.length) { // this is the last call
                                        var min_distance = undefined;
                                        var min_distance_index = undefined;
                                        var address_location = new LatLon(original_location.lat(), original_location.lng());
                                        for (var i = 0; i < addresses.length; i++) {
                                            if (!(original_address.lat && original_address.lon)) {
                                                continue;
                                            }
                                            var candidate_location = new LatLon(addresses[i].lat, addresses[i].lon);
                                            var distance = address_location.distanceTo(candidate_location);
                                            if (min_distance == undefined || distance < min_distance) {
                                                min_distance = distance;
                                                min_distance_index = i;
                                            }
                                        }
                                        var res;
                                        if (min_distance_index == undefined) {
                                            res = null;
                                        } else {
                                            res = addresses[min_distance_index];
                                        }
                                        var callback = that._pendingReverseGeocodeCallback;
                                        that._pendingReverseGeocodeCallback = undefined;
                                        callback(res, original_location.lat(), original_location.lng());
                                    }
                                }, addresses[j]);
                            }


                        } else {
                            var avg = parseInt((high + low) / 2);
                            component.short_name = avg; // take the middle house number
                            place.formatted_address = place.formatted_address.replace(component.long_name, component.short_name);
                        }
                    }
                }
            }
//        }
//        catch (e) {
//            log(e);
//        }

        return place;
    },
    _getAddressComponent: function(place, type) {
        var res = undefined;
        $.each(place.address_components, function (i, component) {
            if (component.types && $.inArray(type, component.types) > -1) {
                res = component;
                return; // break
            }
        });

        return res;
    }
});

var GoogleMapHelper = Object.create({
    config:{
        map_element:undefined,
        map:undefined,
        map_options:{
            zoom:14
        },
        traffic: false
    },
    mapready:false,
    animation_id: 0,
    do_drag: false,
    markers: {},
    info_bubbles: {},

    init: function(config){
        var that = this;
        this.config = $.extend(true, {}, this.config, config);
        this.map = new google.maps.Map(document.getElementById(this.config.map_element), this.config.map_options);

        google.maps.event.addListener(this.map, 'tilesloaded', function () {
            that.mapready = true;
            $(window).trigger("mapready");
        });

        if (this.config.traffic){
            var trafficLayer = new google.maps.TrafficLayer();
            trafficLayer.setMap(this.map)
        }
    },
    zoomMarker: function(marker_name){
        var marker = this.markers[marker_name];
        if (marker){
            this.map.setCenter(marker.getPosition());
            this.map.setZoom(17);
        }
    },
    /*
    animateMarker: animate a marker to a new position
    options:
        name: the name of the marker located in this.markers
        lat: new lat value
        lon: new lon value
        duration: animation duration in seconds (default 2)
        fps: frames per second (default 30)
        callback: a callback to call at the end of the animation
     */
    animateMarker: function(options) {
        var that = this;

        if (! this.markers[options.name]) {
            return false; // unknown marker
        }
        var animation_id = ++this.animation_id;
        var fps = options.fps || 30;
        var duration = options.duration || 2;
        var initial_position = new LatLon(this.markers[options.name].getPosition().lat(), this.markers[options.name].getPosition().lng());
        var final_position = new LatLon(options.lat, options.lon);
        var bearing = initial_position.bearingTo(final_position);
        var distance = initial_position.distanceTo(final_position);
        var steps_count = duration * fps;
        var step_distance = distance / steps_count;
        var steps = [];
        for (var i = 1; i <= steps_count; i++) {
            steps.push(initial_position.destinationPoint(bearing, step_distance * i));
        }

        function animateToStep(step_index) {

            if (animation_id < that.animation_id) { // a new animation has started
                return;
            }

            var new_position = new google.maps.LatLng(steps[step_index].lat(), steps[step_index].lng());
            that.markers[options.name].setPosition(new_position);

            if (step_index % fps == 0) { // once a second, fitMarkers
                that.fitMarkers();
            }

            if (step_index + 1 < steps.length) {
                setTimeout(function() {
                    animateToStep(step_index + 1)
                }, 1000 / fps);
            } else {
                if (options.callback) {
                    options.callback();
                }
            }
        }

        animateToStep(0); // start animation

    },
    fitMarkers: function(){
        var bounds = new google.maps.LatLngBounds();
        var latLng = this.map.getCenter();
        var num_markers = 0;
        $.each(this.markers, function (i, marker) {
            latLng = marker.getPosition();
            num_markers++;
            bounds = bounds.extend(marker.getPosition());

        });
        if (num_markers > 1) {
            this.map.fitBounds(bounds);
        }
        else {
            this.map.setCenter(latLng);
            this.map.setZoom(15);
        }

    },
    fitBubbles: function(){
        var bounds = new google.maps.LatLngBounds();

        var num_markers = 0;
        $.each(this.info_bubbles, function (i, info_bubble) {
            num_markers++;
            bounds = bounds.extend(info_bubble.getPosition());
        });

        if (num_markers > 1) {
            this.map.fitBounds(bounds);
        }

    },
    addMarker: function (address, options) {
        var that = this;
        if (that.mapready) {
            that._addMarker(address, options)
        } else {
            $(window).one("mapready", function() {
                that._addMarker(address, options)
            })
        }
    },
    _addMarker:function (address, options) {
        var that = this;
        var lat = address.lat, lon = address.lon;
        options = $.extend(true, {}, options);
        // remove old marker with the same name or position
        var marker_name = options.marker_name || lat + "_" + lon;
        marker_name = marker_name.split(".").join("_"); // replace . with _
        var old_marker = this.markers[marker_name];
        if (old_marker){
            old_marker.setMap(null);
        }

        // add the new marker
        var latLng = new google.maps.LatLng(lat, lon);
        var markerOptions = {
            map: this.map,
            position:latLng,
            title: "",
            clickable: false
//            animation:google.maps.Animation.DROP
        };
        markerOptions = $.extend(true, markerOptions, options);
        if (options.icon_image){
            markerOptions.icon = new google.maps.MarkerImage(options.icon_image);
        }

        this.markers[marker_name] = new google.maps.Marker(markerOptions);
        if (options.show_info) GoogleMapHelper.showInfo(address.name, this.markers[marker_name], address.type);
        return this.markers[marker_name];
    },
    addAMarker:function (address, options) {
        options = $.extend(true, {}, {icon_image: "/static/images/wb_site/map_marker_A.png", marker_name:"A"}, options);
        return this.addMarker(address, options);
    },
    addBMarker:function (address, options) {
        options = $.extend(true, {}, {icon_image:"/static/images/wb_site/map_marker_B.png", marker_name:"B"}, options);
        return this.addMarker(address, options);
    },
    removeMarker:function (names) {
        var that = this;
        if (names == "all") {
            $.each(this.markers, function (i, marker) {
                marker.setMap(null);
            });
            that.markers = {};
        }
        else {
            $.each(names.split(","), function (i, name) {
                name = name.trim();
                var marker = that.markers[name];
                if (marker) {
                    marker.setMap(null);
                    delete that.markers[name];
                }
            })
        }
    },
    showInfo: function(content, anchor, bubble_name) {
        var info = new InfoBubble({
            content: content,
            hideCloseButton: true,
            borderRadius: 5,
            padding: 5,
            arrowSize: 10
        });
        var old_bubble = this.info_bubbles[bubble_name];
        if (old_bubble) {
            old_bubble.setMap(null);
        }
        this.info_bubbles[bubble_name] = info;
        info.open(this.map, anchor);
        return info;
    },
    setCenter: function(lat, lon) {
        this.map.setCenter(new google.maps.LatLng(lat, lon));
    },
    clearMarkers: function() {
        $.each(this.markers, function(i, marker) {
            marker.setVisible(false);
        });
        $.each(this.info_bubbles, function(i, info_bubble) {
            info_bubble.close();
        });
    },
    setMarkersVisibility: function(visible) {
        $.each(this.markers, function(i, marker) {
            marker.setVisible(visible);
        });
        if (!visible) {
            $.each(this.info_bubbles, function(i, info_bubble) {
                info_bubble.close();
            });
        } else {
            $.each(this.info_bubbles, function(i, info_bubble) {
                info_bubble.open();
            });
        }
    },
    showMarkersByName: function(name) {
        var that = this;
        $.each(this.markers, function(key, marker) {
            marker.setVisible(key == name)
        });

        $.each(this.info_bubbles, function(key, bubble) {
            if (key == name) {
                bubble.open()
            } else {
                bubble.close()
            }
        });
    }

});

var SocialHelper = Object.create({
    config:{
        messages:{
            email:{
                subject: "",
                body: ""
            },
            facebook:{
                share_msg: ""
            },
            twitter:{
                share_msg: ""
            }
        }
    },
    init:function (config) {
        this.config = $.extend(true, {}, this.config, config);
    },
    getEmailShareLink:function (options) {
        options = $.extend(true, {
            subject: this.config.messages.email.subject,
            body: this.config.messages.email.body}, options);
        return "mailto:?subject=" + options.subject + "&body=" + options.body;
    },
    getTwitterShareLink:function (msg) {
        msg = msg || this.config.messages.twitter.share_msg;
        return "http://twitter.com/share?text=" + msg + "&url=http://www.WAYbetter.com";
    },
    getFacebookShareLink:function (mobile) {
        var url = "http://" + ((mobile) ? "m" : "www") + ".facebook.com/dialog/feed?" +
            "&app_id=280509678631025" +
            "&link=http://www.WAYbetter.com" +
            "&picture=http://www.waybetter.com/static/images/wb_site/wb_beta_logo.png" +
            "&name=" + "WAYbetter" +
            //                    "&caption=" +
            "&description=" + encodeURIComponent(this.config.messages.facebook.share_msg) +
            "&redirect_uri=http://www.waybetter.com";
        if (mobile) {
            url += "&display=touch"
        }

        return url;
    },
    getFacebookLikeLink:function (mobile) {
        return "http://" + ((mobile) ? "m" : "www") + ".facebook.com/pages/WAYbetter/131114610286539";
    }
});
