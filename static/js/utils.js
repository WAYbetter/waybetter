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
                if ($(this).hasClass("ui-button")) {
                    $(this).button("disable");
                } else {
				    $(this).attr({disabled: true});
                }
                if ($.mobile && $(this).is(":button")){
                    $(this).button().button("refresh");
                }
			});
		},
		enable: function() {
			return this.each(function() {
                if ($(this).hasClass("ui-button")) {
                    $(this).button("enable");
                } else {
				    $(this).removeAttr('disabled');
                }
                if ($.mobile && $(this).is(":button")){
                    $(this).button().button("refresh");
                }
			});
		},
        set_button_text: function(text) {
            return this.each(function() {
                if ($(this).hasClass("ui-button")) {
                    $(this).button("option", "label", text);
                } else {
                    $(this).text(text).parent().find(".ui-btn-text").text(text);
                }
            })
        },
        set_button_theme: function(theme_swatch) {
            var swatch_re = /-(\w)$/;
            return this.each(function() {
                // for jq-mobile
                var parent_element = $(this).closest(".ui-btn");
                if (parent_element.length) {
                    var class_list = parent_element.attr("class").split(/\s+/);
                    var new_class_list = [];
                    $(this).attr("data-theme", theme_swatch);
                    $.each(class_list, function(i, cls) {
                        var matches = cls.match(swatch_re);
                        if (matches && matches[1] != theme_swatch) {
                            new_class_list.push(cls.replace(swatch_re, "-" + theme_swatch));
                        } else {
                            new_class_list.push(cls);
                        }
                    });
                    parent_element.attr("data-theme", theme_swatch).attr("class", new_class_list.join(" "));
                    $(this).button("refresh");
                }
            })
        },
        swap: function(b) {
            b = jQuery(b)[0];
            var a = this[0],
                    a2 = a.cloneNode(true),
                    b2 = b.cloneNode(true),
                    stack = this;

            a.parentNode.replaceChild(b2, a);
            b.parentNode.replaceChild(a2, b);

            stack[0] = a2;
            return this.pushStack(stack);
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

flashError = function(msg) {
    flashMessage(msg, "error");
};

flashMessage = function(msg, extra_class) {
    var $flash = $("#flash");
    if ($flash.length == 0) {
        $("body").append("<div id='flash'></div>");
        $flash = $("#flash");
    }

    // init flasher
    $flash.stopTime("show_flash").stopTime("hide_flash");
    $flash.removeClass("show").removeClass(extra_class);

    $flash.oneTime(10, "show_flash", function() {
        $flash.empty().html(msg).addClass("show");
        if (extra_class) {
            $flash.addClass(extra_class);
        }
        $flash.css({ "margin-left": -($flash.outerWidth() / 2) + "px" });
        $flash.oneTime(5000, "hide_flash", function() {
            $flash.removeClass("show").removeClass(extra_class);
        }, 5000);
    });
};

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
            var func = window.parentSandboxBridge[func_name];
            return func.apply(window.parentSandboxBridge, new_args);
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

function getAccordionPosition(elements, key, val) {
    // returns the div after which to append the new header and div, or
    // undefined if no such div exists (i.e., the new header and div should be first).
    // assumes existing accordion elements in the page are ordered.

    var append_after = undefined;
    $.each(elements, function(i, e) {
        if ($(this).data(key) <= val) {
            append_after = this;
        }
        else {
            return false; // break
        }
    });
    return append_after;
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

Array.prototype.sum = function(){
    for (var i = 0,sum = 0; i < this.length; sum += this[i++]);
    return sum;
};

function getRandomInt(min, max)
{
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

window.log = function(){
  log.history = log.history || [];   // store logs to an array for reference
  log.history.push(arguments);
  if(this.console){
    console.log( Array.prototype.slice.call(arguments) );
  }
};

window.logargs = function(context){
  // grab the calling functions arguments
  log(context,arguments.callee.caller.arguments);
}

function gaHitPage(url) {
    try {
        _gaq.push(['_trackPageview', '/' + url]);
    } catch(e){
        log(e);
    }
}

$(function() {
    var subject = "WAYbetter - מוניות לכולם, בחצי מחיר";
    var body = "בשבועות הקרובים תשיק חברת WAYbetter שירות מוניות מהפכני ברמת החייל.%0Aהשירות יאפשר להזמין חינם מונית בסמארטפון או באינטרנט ולשלם על הנסיעה חצי מחיר (!).%0Aבאמצעות מערכת WAYbetter ניתן להזמין נסיעה המשפרת את יעילות המונית באמצעות חיבור ביניכם לבין משתמשים אחרים הנוסעים לאותו הכיוון. כך אתם יכולים ליהנות משירות תחבורה ברמה הגבוהה ביותר, במחיר שווה לכל כיס.%0A%0Aרוצה לקחת חלק?%0Awww.waybetter.com";
    var social_msg = "WAYbetter משיקה מערכת שתוזיל נסיעות מונית בתל אביב לחצי מחיר!%0Aקחו חלק בניסוי הפרטי www.waybetter.com";

    window.shareByEmail = function(){
        window.location.href = "mailto:?subject=" + subject + "&body=" + body;
    };
    window.shareByTwitter = function(){
        window.location.href = "http://twitter.com/share?text=" + social_msg + "&url=http://www.WAYbetter.com";
    };
    window.shareByFB = function(){
        window.location.href = "http://www.facebook.com/dialog/feed?" +
                "&app_id=280509678631025" +
                "&link=http://www.WAYbetter.com" +
                "&picture=http://www.waybetter.com/static/images/wb_site/wb_beta_logo.png" +
                "&name=" + "WAYbetter" +
//                    "&caption=" +
                "&description=" + social_msg +
                "&redirect_uri=http://www.waybetter.com";
    };
}());

