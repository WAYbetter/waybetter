var PhoneGapHelper = Object.create({
    config: {
        urls: {
            is_user_authenticated   : ""
        }
    },
    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);
    },

    isUserAuthenticated: function(callbacks, async) {
        if (typeof async === undefined) {
            async = true;
        }
        if (! callbacks ) {
            return;
        }
        var that = this;
        log("checking user auth");
        $.ajax({
            url:that.config.urls.is_user_authenticated,
            dataType:"json",
            async:async,
            success:function (result) {
                if (result && result[0] === true) {
                    $.each(callbacks, function(i, callback) {
                        callback(true, result[1]);
                    });
                } else {
                    $.each(callbacks, function(i, callback) {
                        callback(false);
                    });
                }
            },
            error:function () {
                log("error checking user auth");
                $.each(callbacks, function(i, callback) {
                    callback(false);
                });
            }

        })
     }
});

