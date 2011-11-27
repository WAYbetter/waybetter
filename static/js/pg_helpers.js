var PhoneGapHelper = Object.create({
    config: {
        urls: {
            is_user_authenticated   : ""
        }
    },
    init: function(config) {
        this.config = $.extend(true, {}, this.config, config);
    },

    isUserAuthenticated: function(is_callback, isnt_callback) {
         var that = this;
         log("checking user auth");
         $.ajax({
             url: that.config.urls.is_user_authenticated,
             dataType: "json",
             success: function(result) {
                 if (result && result[0] === true) {
                     if (is_callback)
                         is_callback(result[1]);
                 } else {
                     if (isnt_callback)
                         isnt_callback()
                 }
             },
             error: function() {
                 log("error checking user auth");
                 if (isnt_callback) {
                     isnt_callback()
                 }
             }

         })
     }

});

