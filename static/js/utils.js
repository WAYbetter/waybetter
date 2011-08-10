Object.create = Object.create || function (p) {
    if ( arguments.length != 1 ) {
        throw new Error("Can't simulate 2nd arg");
    }
    function f() {};
    f.prototype = p;
    return new f();
};

(function($) {
	$.fn.extend({
		disable: function() {
			return this.each(function() {
				$(this).attr({disabled: true});
			});
		},
		enable: function() {
			return this.each(function() {
				$(this).removeAttr('disabled');
			});
		},
        set_button_text: function(text) {
            return this.each(function() {
                $(this).parent().find(".ui-btn-text").text(text);
            })
        }
	});

})(jQuery);

//custom jQuery selector
jQuery.extend(jQuery.expr[':'], {
    focus: function(element) {
        return element == document.activeElement;
    }
});

/**
 * defineClass( ) -- a utility function for defining JavaScript classes.
 *
 * This function expects a single object as its only argument.  It defines
 * a new JavaScript class based on the data in that object and returns the
 * constructor function of the new class.  This function handles the repetitive
 * tasks of defining classes: setting up the prototype object for correct
 * inheritance, copying methods from other types, and so on.
 *
 * The object passed as an argument should have some or all of the
 * following properties:
 *
 *      name: The name of the class being defined.
 *            If specified, this value will be stored in the classname
 *            property of the prototype object.
 *
 *    extend: The constructor of the class to be extended. If omitted,
 *            the Object( ) constructor will be used. This value will
 *            be stored in the superclass property of the prototype object.
 *
 * construct: The constructor function for the class. If omitted, a new
 *            empty function will be used. This value becomes the return
 *            value of the function, and is also stored in the constructor
 *            property of the prototype object.
 *
 *   methods: An object that specifies the instance methods (and other shared
 *            properties) for the class. The properties of this object are
 *            copied into the prototype object of the class. If omitted,
 *            an empty object is used instead. Properties named
 *            "classname", "superclass", and "constructor" are reserved
 *            and should not be used in this object.
 *
 *   statics: An object that specifies the static methods (and other static
 *            properties) for the class. The properties of this object become
 *            properties of the constructor function. If omitted, an empty
 *            object is used instead.
 *
 *   borrows: A constructor function or array of constructor functions.
 *            The instance methods of each of the specified classes are copied
 *            into the prototype object of this new class so that the
 *            new class borrows the methods of each specified class.
 *            Constructors are processed in the order they are specified,
 *            so the methods of a class listed at the end of the array may
 *            overwrite the methods of those specified earlier. Note that
 *            borrowed methods are stored in the prototype object before
 *            the properties of the methods object above. Therefore,
 *            methods specified in the methods object can overwrite borrowed
 *            methods. If this property is not specified, no methods are
 *            borrowed.
 *
 *  provides: A constructor function or array of constructor functions.
 *            After the prototype object is fully initialized, this function
 *            verifies that the prototype includes methods whose names and
 *            number of arguments match the instance methods defined by each
 *            of these classes. No methods are copied; this is simply an
 *            assertion that this class "provides" the functionality of the
 *            specified classes. If the assertion fails, this method will
 *            throw an exception. If no exception is thrown, any
 *            instance of the new class can also be considered (using "duck
 *            typing") to be an instance of these other types.  If this
 *            property is not specified, no such verification is performed.
 **/
function defineClass(data) {
    // Extract the fields we'll use from the argument object.
    // Set up default values.
    var classname = data.name;
    var superclass = data.extend || Object;
    var constructor = data.construct || function( ) {};
    var methods = data.methods || {};
    var statics = data.statics || {};
    var borrows;
    var provides;

    // Borrows may be a single constructor or an array of them.
    if (!data.borrows) borrows = [];
    else if (data.borrows instanceof Array) borrows = data.borrows;
    else borrows = [ data.borrows ];

    // Ditto for the provides property.
    if (!data.provides) provides = [];
    else if (data.provides instanceof Array) provides = data.provides;
    else provides = [ data.provides ];

    // Create the object that will become the prototype for our class.
    var proto = new superclass( );

    // Delete any noninherited properties of this new prototype object.
    for(var p in proto)
        if (proto.hasOwnProperty(p)) delete proto[p];

    // Borrow methods from "mixin" classes by copying to our prototype.
    for(var i = 0; i < borrows.length; i++) {
//        var c = data.borrows[i];
//        borrows[i] = c;
        var c = borrows[i];
        // Copy method properties from prototype of c to our prototype
        for(var p in c.prototype) {
            if (typeof c.prototype[p] != "function") continue;
            proto[p] = c.prototype[p];
        }
    }
    // Copy instance methods to the prototype object
    // This may overwrite methods of the mixin classes
    for(var p in methods) proto[p] = methods[p];

    // Set up the reserved "constructor", "superclass", and "classname"
    // properties of the prototype.
    proto.constructor = constructor;
    proto.superclass = superclass;
    // classname is set only if a name was actually specified.
    if (classname) proto.classname = classname;

    // Verify that our prototype provides all of the methods it is supposed to.
    for(var i = 0; i < provides.length; i++) {  // for each class
        var c = provides[i];
        for(var p in c.prototype) {   // for each property
            if (typeof c.prototype[p] != "function") continue;  // methods only
            if (p == "constructor" || p == "superclass") continue;
            // Check that we have a method with the same name and that
            // it has the same number of declared arguments.  If so, move on
            if (p in proto &&
                typeof proto[p] == "function" &&
                proto[p].length == c.prototype[p].length) continue;
            // Otherwise, throw an exception
            throw new Error("Class " + classname + " does not provide method "+
                            c.classname + "." + p);
        }
    }

    // Associate the prototype object with the constructor function
    constructor.prototype = proto;

    // Copy static properties to the constructor
    for(var p in statics) constructor[p] = data.statics[p];

    // Finally, return the constructor function
    return constructor;
}

function update_options(options) {
    var config = {
        parent_id_selector:     "",
        target_id_selector:     "", // optional, can be returned from server
        url:                    ""
    };
    $.extend(true, config, options);
    $(config.parent_id_selector).unbind("change.update_options").bind("change.update_options", function() {
        update_options(options);    
    });
    $.ajax({
        url:        config.url,
        data:       $(config.parent_id_selector).serialize(),
        dataType:   'json',
        success:    function(data) {
            if (! data.options) {
                return
            }
            var target_id = data.target_id_selector || config.target_id_selector;
            if (! target_id) {
                throw("no target_id!");
            }

            $(target_id).empty();
            $.each(data.options, function(i, option) {
                var $option = $("<option>").val(option[0]).text(option[1]);
                if ('selected_option' in data && data.selected_option == option[0]) {
                    $option.attr("selected", "selected");
                }
                $(target_id).append($option);
                
            });
            $(target_id).trigger('change');

        }

    });
}

function air() {
    if (arguments.length < 1) {
        throw "Invalid arguments: must pass function name"
    }

    // for some reason AIR does not support array.pop, shift, slice etc. - doing it the hard way
    var func_name = arguments[0];
    var new_args = [];

    for(var i=1; i<arguments.length; ++i) {
        new_args[i-1] = arguments[i];
    }
    
    if (window.parentSandboxBridge) {
        try {
            return window.parentSandboxBridge[func_name].apply(window.parentSandboxBridge, new_args);
        } catch (e) {
            return false;
        }
    }
    return false;
}

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
    construct:  function(args) {
        var that = this;
        $.each(args, function(k, v) {
            that[k] = v;
        });
    },
    methods:    {
        isResolved:     function() {
            return (this.lon && this.lat) && (this.raw == $('#id_geocoded_' + this.address_type + '_raw').val());
        },
        populateFields: function () {
            var that = this;
            $.each(Address._fields, function(i, e) {
                $('#id_' + that.address_type + '_' + e).val(that[e]);
            });

            $('#id_' + that.address_type + '_raw').removeClass("placeheld"); // placeheld plugin only removes class on focus
            $('#id_geocoded_' + that.address_type + '_raw').val(that.raw);
            return $('#id_' + that.address_type + '_raw');
        },
        clearFields: function (including_raw) {
            Address.clearAddressFields(this.address_type, including_raw);
        }
    },
    statics:    {
        //TODO_WB: generated from order fields.
        _fields:    ["raw", "city", "street_address", "house_number", "country", "geohash", "lon", "lat"],
        // factory methods
        fromFields:         function(address_type) {
            var args = { address_type: address_type };
            $.each(Address._fields, function (i, e) {
               args[e] =  $('#id_' + address_type + '_' + e).val();
            });

            return new Address(args);
        },
        fromInput:          function(input_element) {
            var address_type = $(input_element)[0].name.split("_")[0];
            return Address.fromFields(address_type);
        },
        fromServerResponse: function(response, address_type) {
            var args = { address_type: address_type };
            if (response) {
                $.each(Address._fields, function (i, e) {
                    args[e] = response[e]
                });
                return new Address(args);
            } else {
                return new Address({});
            }
        },
        fromJSON:           function(json_string) {
            var json = JSON.parse(json_string);
            return Address.fromServerResponse(json, json.address_type);
        },

        // utility methods
        clearAddressFields: function(address_type, including_raw) {
            $.each(Address._fields, function(i,e) {
                if (e != 'raw' || including_raw) {
                    $("#id_" + address_type + "_" + e).val("");
                }
            });
            $('#id_geocoded_' + address_type + '_raw').val('');
        }
    }
});

function openDialog(title, html, close_function){
    var $dialog = $('<div></div>')
            .html(html)
            .dialog({
                autoOpen: false,
                close: close_function,
                title: title,
                resizable: false,
                modal: true,
                position: ["center", 100],
                draggable: false,
                zIndex:2000
            });
    $dialog.append($("<button class='dialog-close-btn wb_button blue'>OK</button>").click(function(){
        $dialog.dialog('close');
    }));
    $dialog.dialog('open');
}

var easydate_config = {
    locale: {
        "future_format": "%s %t",
        "past_format": "%s %t",
        "second": "שנייה",
        "seconds": "שניות",
        "minute": "דקה",
        "minutes": "דקות",
        "hour": "שעה",
        "hours": "שעות",
        "day": "יום",
        "days": "ימים",
        "week": "שבוע",
        "weeks": "שבועות",
        "month": "חודש",
        "months": "חודשים",
        "year": "שנה",
        "years": "שנים",
        "yesterday": "אתמול",
        "tomorrow": "מחר",
        "now": "כעת",
        "ago": "לפני",
        "in": "בעוד"
    },
    units: [
        { name: "now", limit: 59 },
        { name: "minute", limit: 3600, in_seconds: 60 },
        { name: "hour", limit: 86400, in_seconds: 3600  },
        { name: "yesterday", limit: 172800, past_only: true },
        { name: "tomorrow", limit: 172800, future_only: true },
        { name: "day", limit: 604800, in_seconds: 86400 },
        { name: "week", limit: 2629743, in_seconds: 604800  },
        { name: "month", limit: 31556926, in_seconds: 2629743 },
        { name: "year", limit: Infinity, in_seconds: 31556926 }
]
};

function getFullDate(date_obj){
    return date_obj.getDate() + '/' + (date_obj.getMonth() + 1) + '/' + date_obj.getFullYear();
}

function getFullTime(date_obj){
    var minutes = date_obj.getMinutes();
    var hours = date_obj.getHours();
    var s = hours + ":";
    if (minutes < 10) {
        s += "0" + minutes
    } else {
        s += minutes
    }
    return s;
}

Array.prototype.unique = function() {
    var unique_array = [];
    for (var i = 0; i < this.length; ++i) {
        var val = this[i];
        if (unique_array.indexOf(val) === -1) {
            unique_array.push(val)
        }
    }
    return unique_array;
};