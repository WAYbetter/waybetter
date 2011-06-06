var OrderTracker = Object.create({
            channel : undefined,
            socket : undefined,
            PREVENT_TIMEOUT_INTERVAL : 1000 * 60 * 110, // channel closes after 120 minutes

            config: {
                ASSIGNED : "",
                PENDING : "",
                ACCEPTED : "",
                ORDER_FAILED : "",
                ORDER_MAX_WAIT_TIME : "",
                FAILED_MSG : "",
                init_token : "",
                init_tracker_history : "",
                get_tracker_init_url: "",
                please_wait_msg: "",
                close_msg: "",
                changes_msg: "",
                minute_label: "",
                minutes_label: "",
                pickup_in_msg: "",
                order_finished_msg: "",
                connection_error_msg: "",
                countdown_finished_msg: ""
            },

            init: function(config) {
                this.config = $.extend(true, {}, this.config, config);
                if (config.init_token && config.init_tracker_history) {
                    this.restoreOrderTracker(config.init_token, config.init_tracker_history);
                }
            },

            restoreOrderTracker: function(token, tracker_history) {
                this.openChannel(token);
                $(this).stopTime("prevent_channel_timeout");
                $(this).oneTime(this.PREVENT_TIMEOUT_INTERVAL, "prevent_channel_timeout", this.resetOrderTracker);
                if (tracker_history) {
                    for (var count = 0; count < tracker_history.length; count++) {
                        this.processOrder(tracker_history[count]);
                    }
                }
            },

            openChannel: function(token) {
                $("#wcs-iframe").remove();

                var that = this;
                this.channel = new goog.appengine.Channel(token);
                this.socket = this.channel.open();

                this.socket.onerror = this.resetOrderTracker;
                this.socket.onclose = this.resetOrderTracker;
                this.socket.onmessage = function(msg) {
                    that.processOrder(msg.data);
                };
            },

            resetOrderTracker: function() {
                // when called by socket, this == socket
                OrderTracker.setErrorState.call(OrderTracker, true);
                if (OrderTracker.socket) {
                    OrderTracker.socket.onclose = function() {
                        return true;  // avoid onclose loop
                    };
                    OrderTracker.socket.close();
                }

                $.ajax({
                            url: OrderTracker.config.get_tracker_init_url,
                            dataType: "json",
                            cache: false,
                            success: function (response) {
                                OrderTracker.setErrorState.call(OrderTracker, false);
                                OrderTracker.restoreOrderTracker.call(OrderTracker, response.token, response.tracker_history);
                            },
                            error: function () {
                                setTimeout(OrderTracker.resetOrderTracker, 3000); // try again in 3 seconds
                            }

                        })
            },

            setErrorState: function(is_error) {
                var orders = $("#order_tracker > [id^='order_']");
                for (var i = 0; i < orders.length; i++) {
                    var $order = $(orders[i]);
                    if ($order.data("status") == this.config.PENDING || $order.data("status") == this.config.ASSIGNED) {
                        if (is_error) {
                            $order.removeClass("searching").addClass("error").find(".content_container").addClass("connection_error");
                            $order.find(".connection_error_label").show();
                        }
                        else {
                            $order.removeClass("error").addClass("searching").find(".content_container").removeClass("connection_error");
                            $order.find(".connection_error_label").hide();
                        }
                    }
                }
            },

            updateOrder: function(order) {
                var $order = this.getOrder(order);
                if (! $order) {
                    $order = this.buildOrder(order);
                }
                var $station = $("#station_" + order.pk),
                        $station_phone = $("#station_phone_" + order.pk),
                        $info = $("#info_" + order.pk),
                        $indicator = $("#indicator_" + order.pk),
                        $close_btn = $("#close_btn_" + order.pk);

                var that = this;
                switch (order.status) {
                    case this.config.PENDING:
                        $order.removeClass("assigned").addClass("pending").data("status", order.status);
                        $indicator.addClass("searching").text(this.config.please_wait_msg);
                        $info.addClass("searching").text(order.info);
                        $station.text(order.station).effect("highlight", 1000);
                        break;

                    case this.config.ASSIGNED:
                        $order.removeClass("pending").addClass("assigned").data("status", order.status);
                        $indicator.addClass("searching").text(this.config.please_wait_msg);
                        $info.addClass("searching").text(order.info).effect("highlight", 1000);
                        $station.text(order.station);
                        break;

                    case  this.config.ACCEPTED :
                        $order.removeClass("pending assigned").addClass("accepted").data("status", order.status);

                        if (! order.pickup_time_sec) {
                            $info.text(this.config.order_finished_msg);
                        }
                        // future order, show pickup mode
                        else {
                            $indicator.removeClass("searching").addClass("accepted");
                            $station.text(order.station);
                            $info.removeClass("searching").addClass("accepted").text(order.info).effect("highlight", 1000);
                            $station_phone.text(this.config.changes_msg + order.station_phone).fadeIn();

                            // stop previously installed timers and set a new one
                            $indicator.stopTime("pickup_timer_" + order.id);

                            var minutes = Math.floor(order.pickup_time_sec / 60),
                                    seconds_remainder = order.pickup_time_sec % 60,
                                    initial_value = (seconds_remainder) ? minutes + 1 : minutes,
                                    minute_label = (initial_value == 1) ? this.config.minute_label : this.config.minutes_label;

                            $indicator.val(initial_value).text(this.config.pickup_in_msg + " " + initial_value + " " + minute_label + " (" + order.pickup_hour + ")")
                                    .oneTime(seconds_remainder * 1000, "pickup_timer_" + order.pk, function() {
                                that.updateTimer(order)
                            });

                        }
                        break;

                    case  this.config.ORDER_FAILED :
                        $order.removeClass("pending assigned").addClass("failed").data("status", order.status);
                        $station.remove();
                        $indicator.remove();
                        $info.removeClass("searching").addClass("failed").text(this.config.FAILED_MSG);
                        $close_btn.fadeIn().click(function() {
                            $order.slideUp();
                        });
                        break;
                }
            },

            buildOrder: function(order) {
                var $address_list =
                        $("<ul class='tracker_address_list'></ul>")
                                .append($("<li class='tracker_from'></li>").text(order.from_raw))
                                .append($("<li class='tracker_to'></li>").text(order.to_raw)),
                        $info_container = $("<div class='tracker_info_container'></div>")
                                .append($("<span class='tracker_station'></span>").attr('id', 'station_' + order.pk))
                                .append($("<span class='tracker_info'></span>").attr('id', 'info_' + order.pk)),
                        $details_container = $("<div class='tracker_details_container'></div>")
                                .append($("<button class='tracker_button wb_button gray'></button>").text(this.config.close_msg).attr('id', 'close_btn_' + order.pk).hide())
                                .append($("<div class='tracker_indicator'></div>").attr('id', 'indicator_' + order.pk))
                                .append($("<div class='tracker_station_phone'></div>").attr('id', 'station_phone_' + order.pk).hide());

                var $content_container = $("<div class='content_container'></div>").append($address_list).append($info_container).append($details_container),
                        $error_label = $("<div class='connection_error_label'></div>").text(this.config.connection_error_msg).hide(),
                        $order = $("<div class='tracker_order'></div>").attr('id', 'order_' + order.pk).append($content_container).append($error_label);

                if (order.to_raw == "") {
                    $address_list.find(".tracker_to").hide();
                }

                // add this order to the tracker and set a timer to check it is updated
                var that = this;
                $($order).hide().prependTo("#order_tracker").slideDown('slow').oneTime(1000 * this.config.ORDER_MAX_WAIT_TIME, function() {
                    var status = $(this).data("status");
                    if (status == that.config.PENDING || status == that.config.ASSIGNED) {
                        that.resetOrderTracker();
                    }
                });

                return $order;
            },

            updateTimer: function(order) {
                var $order = this.getOrder(order),
                        $station = $("#station_" + order.pk),
                        $station_phone = $("#station_phone_" + order.pk),
                        $info = $("#info_" + order.pk),
                        $indicator = $("#indicator_" + order.pk),
                        $close_btn = $("#close_btn_" + order.pk);

                var new_val = Math.max(0, $indicator.val() - 1);
                if (new_val == 0) {
                    $info.removeClass("accepted").text(this.config.countdown_finished_msg).effect("highlight", 1000);
                    $station.fadeOut();
                    $indicator.fadeOut();
                    $close_btn.fadeIn().click(function() {
                        $order.slideUp();
                    });
                    $station_phone.addClass("button_present");
                }
                else {
                    var that = this,
                            minute_label = (new_val == 1) ? this.config.minute_label : this.config.minutes_label;
                    $indicator.text(this.config.pickup_in_msg + " " + new_val + " " + minute_label + " (" + order.pickup_hour + ")").effect("highlight", 1000)
                            .oneTime(60 * 1000, "pickup_timer_" + order.pk, function() {
                        that.updateTimer(order)
                    });
                }

                $indicator.val(new_val);
            },


            processOrder: function(msg) {
                try {
                    var order = $.parseJSON(msg);

                    if (this.isValidOrder(order)) {
                        this.updateOrder(order);
                    }
                }
                catch(e) {
                    // handle JSON parsing errors here
                }
            },

            getOrder: function(order) {
                var $order = $("#order_tracker #order_" + order.pk);
                if ($order.length == 0)
                    return undefined;
                else
                    return $order.first();
            },

            isValidOrder: function(order) {
                return Boolean(order.pk > 0);  // small test that the msg is valid
            }
});