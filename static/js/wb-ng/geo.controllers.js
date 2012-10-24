var module = angular.module('wbGeoControllers', []);

module.controller("GoogleMapController", function ($timeout) {
    function get_marker_image (icon) {
        console.log("get_marker_image: " + angular.toJson(icon));
        var anchor_point, marker;
        if (icon) {
            var icon_size = new google.maps.Size(icon.width, icon.height);
            var hd_icon_size = new google.maps.Size(icon.width * 2, icon.height * 2);
            var hd_icon_url = icon.url.replace(".png", "_retina.png");

            if (icon.anchor === "bottom") {
                anchor_point = new google.maps.Point(icon.width / 2, icon.height);
            } else { // middle
                anchor_point = new google.maps.Point(icon.width / 2, icon.height / 2);
            }

            if (window.devicePixelRatio && window.devicePixelRatio >= 2) {
                console.log("using retina image", window.devicePixelRatio, hd_icon_url);
                marker = new google.maps.MarkerImage(hd_icon_url, hd_icon_size, undefined, anchor_point, icon_size);
            } else {
                console.log("using normal image", icon.url);
                marker = new google.maps.MarkerImage(icon.url, icon_size, undefined, anchor_point, icon_size);
            }
        }
        return marker;
    }

    return {
        map:undefined,
        markers:{},
        animations:{},

        center_map: function(lat, lng) {
            this.map.setCenter(new google.maps.LatLng(lat, lng));
        },

        get_markers:function () {
            return this.markers;
        },

        get_marker:function (name) {
            return this.markers[name];
        },

        add_marker:function (address, options) {
            var lat = address.lat,
                lng = address.lng;

            options = angular.extend({
                name:(lat + "_" + lng).split(".").join("_"), // replace . with _
                map:this.map,
                position:new google.maps.LatLng(lat, lng),
                title:"",
                clickable:false

            }, options);

            options.icon = get_marker_image(options.icon);
            options.optimized = false;

            this.remove_marker(options.name);
            var marker = new google.maps.Marker(options);
            this.markers[options.name] = marker;
            return marker;
        },

        remove_marker:function (name) {
            var old_marker = this.markers[name];
            if (old_marker) {
                old_marker.setMap(null);
                delete this.markers[name];
            }
        },

        fit_markers:function () {
            var self = this;
            var bounds = new google.maps.LatLngBounds();
            var num_markers = 0;
            var latLng;
            angular.forEach(self.markers, function (marker, i) {
                latLng = marker.getPosition();
                num_markers++;
                bounds = bounds.extend(latLng);
            });
            if (num_markers > 1) {
                self.map.fitBounds(bounds);
            }
            else if (num_markers == 1) {
                self.map.setCenter(latLng);
                self.map.setZoom(15);
            }
        },

        animate_marker:function (marker_name, destination, config) {
            var that = this;

            var marker = this.markers[marker_name];
            if (!marker) {
                return;
            }

            if (this.animations[marker_name] == undefined) {
                this.animations[marker_name] = 0;
            }
            var animation_id = ++this.animations[marker_name];
            var fps = config.fps || 30;
            var duration = config.duration || 2;

            var initial_position = new LatLon(marker.getPosition().lat(), marker.getPosition().lng());
            var final_position = new LatLon(destination.lat, destination.lng);
            var bearing = initial_position.bearingTo(final_position);
            var distance = initial_position.distanceTo(final_position);

            var steps_count = duration * fps;
            var step_distance = distance / steps_count;
            var steps = [];
            for (var i = 1; i <= steps_count; i++) {
                steps.push(initial_position.destinationPoint(bearing, step_distance * i));
            }

            function animateToStep(step_index) {

                if (animation_id < that.animations[marker_name]) { // a new animation has started
                    return;
                }

                var new_position = new google.maps.LatLng(steps[step_index].lat(), steps[step_index].lng());
                marker.setPosition(new_position);

//                if (step_index % fps == 0) { // once a second, fitMarkers
//                    that.fit_markers();
//                }

                if (step_index + 1 < steps.length) {
                    $timeout(function () {
                        animateToStep(step_index + 1)
                    }, 1000 / fps);
                } else {
                    if (config.callback) {
                        config.callback();
                    }
                }
            }

            animateToStep(0); // start animation
        }
    }
});

