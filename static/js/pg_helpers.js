var PhoneGapHelper = Object.create({
    passenger_token:undefined,
    passenger_name:undefined,
    messages:{},
    config:{
        urls:{
            is_user_authenticated:"",
            get_messages:""
        }
    },
    _saveToken:function () {
        console.log("saveing token: " + this.passenger_token);

        localStorage.setItem('passenger_token', this.passenger_token);
        localStorage.setItem('passenger_name', this.passenger_name);
    },
    _loadToken:function () {
        this.passenger_name = localStorage.getItem('passenger_name');
        this.passenger_token = localStorage.getItem('passenger_token');
        console.log("loading token: " + this.passenger_token);

    },
    init:function (config) {
        this.config = $.extend(true, {}, this.config, config);
        this.getMessages();
        this._loadToken();
    },

    isUserAuthenticated:function (callbacks, async) {
        var that = this;
        if (typeof async === undefined) {
            async = true;
        }
        if (!callbacks) {
            return;
        }
        if (that.passenger_token) {
            console.log("passenger found using token: " + that.passenger_token);
            $.each(callbacks, function (i, callback) {
                callback(true, that.passenger_name);
            });
            return; // no need for further action
        }
        log("checking user auth");
        $.ajax({
            url:that.config.urls.is_user_authenticated,
            dataType:"json",
            async:async,
            success:function (result) {
                if (result && result[0] === true) {
                    if (result[2]) { // we received a login_token
                        that.setPassengerToken(result[2], result[1]);
                    }
                    $.each(callbacks, function (i, callback) {
                        callback(true, result[1]);
                    });
                } else {
                    $.each(callbacks, function (i, callback) {
                        callback(false);
                    });
                }
            },
            error:function () {
                log("error checking user auth");
                $.each(callbacks, function (i, callback) {
                    callback(false);
                });
            }

        })
    },
    getMessages:function () {
        var that = this;
        $.ajax({
            url:that.config.urls.get_messages,
            dataType:"json",
            success:function (result) {
                that.messages = result
            }
        });
    },
    setPassengerToken:function (token, username) {
        console.log("setPassengerToken: " + token + ", " + username);
        var that = this;
        that.passenger_name = username;
        that.passenger_token = token;
        that._saveToken();
    },
    logout:function () {
        this.passenger_token = "";
        this.passenger_name = "";
        this._saveToken();
    },
    addPassengerToken:function (options) {
        if (this.passenger_token) {
            return($.extend(options, {passenger_token:this.passenger_token}));
        } else {
            return options;
        }
    },
    registerAjaxHandlers:function () {
        $(document).ajaxStart(function () {
            console.log("ajaxStart");
            $.mobile.showPageLoadingMsg();

        });
        $(document).ajaxSend(function () {
            console.log("ajaxSend");
            $.mobile.showPageLoadingMsg();

        });
        $(document).ajaxStop(function () {
            console.log("ajaxStop");
            $.mobile.hidePageLoadingMsg();
        });
    }

});

