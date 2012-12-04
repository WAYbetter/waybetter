Object.create = Object.create || function (p) {
    if ( arguments.length != 1 ) {
        throw new Error("Can't simulate 2nd arg");
    }
    function f() {};
    f.prototype = p;
    return new f();
};

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
function getRenderedSize(text, referenceElement) {
    var sizer = document.createElement('DIV');
    sizer.id = 'sizer_id';
    sizer.style['display'] = 'inline';
    sizer.style['position'] = 'absolute';
    var referenceStyle = document.defaultView.getComputedStyle(referenceElement, null);
    sizer.style['fontFamily'] = referenceStyle['fontFamily'];
    sizer.style['fontSize'] = referenceStyle['fontSize'];
    sizer.style['visibility'] = 'hidden';
    sizer.innerHTML = text;

    document.body.appendChild(sizer);

    var size = {width: sizer.offsetWidth, height: sizer.offsetHeight};

    document.body.removeChild(sizer);
    delete sizer;
    return size;

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

function getFullDate(date_obj){
    return date_obj.getDate() + '/' + (date_obj.getMonth() + 1) + '/' + date_obj.getFullYear();
}

function getFullTime(date_obj){
    var minutes = date_obj.getMinutes();
    var hours = date_obj.getHours();
    return ((hours < 10) ? "0" + hours : hours) + ":" + ((minutes < 10) ? "0" + minutes : minutes);
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

String.prototype.endsWith = function(suffix) {
    var pos = this.length - suffix.length;
    return this.indexOf(suffix, pos) === pos;
};

String.prototype.startsWith = function(prefix) {
    return this.indexOf(prefix, 0) === 0;
};

String.prototype.format = function() {
  var args = arguments;
  return this.replace(/{(\d+)}/g, function(match, number) {
    return typeof args[number] != 'undefined'
      ? args[number]
      : match
    ;
  });
};

function getRandomInt(min, max) {
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
};

function gaHitPage(url) {
    try {
        _gaq.push(['_trackPageview', '/' + url]);
    } catch(e){
        log(e);
    }
}

function logGAEvent(category, action, opt_label, opt_value, opt_noniteraction) {
    var ga_args = ['_trackEvent'];
    $.each(arguments, function(i, e) {
        ga_args.push(e)
    });

    try {
        gaHitPage("ga_events/" + category.replace(/\s/g, '_') + "/" + action.replace(/\s/g, '_'));
        return _gaq.push(ga_args);
    } catch(e){
        log(e);
        return 3;
    }
}

/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */
/*  Latitude/longitude spherical geodesy formulae & scripts (c) Chris Veness 2002-2011            */
/*   - www.movable-type.co.uk/scripts/latlong.html                                                */
/*                                                                                                */
/*  Sample usage:                                                                                 */
/*    var p1 = new LatLon(51.5136, -0.0983);                                                      */
/*    var p2 = new LatLon(51.4778, -0.0015);                                                      */
/*    var dist = p1.distanceTo(p2);          // in km                                             */
/*    var brng = p1.bearingTo(p2);           // in degrees clockwise from north                   */
/*    ... etc                                                                                     */
/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */

/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */
/*  Note that minimal error checking is performed in this example code!                           */
/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */


/**
 * Creates a point on the earth's surface at the supplied latitude / longitude
 *
 * @constructor
 * @param {Number} lat: latitude in numeric degrees
 * @param {Number} lon: longitude in numeric degrees
 * @param {Number} [rad=6371]: radius of earth if different value is required from standard 6,371km
 */
function LatLon(lat, lon, rad) {
    if (typeof(rad) == 'undefined') rad = 6371;  // earth's mean radius in km
    // only accept numbers or valid numeric strings
    this._lat = typeof(lat) == 'number' ? lat : typeof(lat) == 'string' && lat.trim() != '' ? +lat : NaN;
    this._lon = typeof(lon) == 'number' ? lon : typeof(lon) == 'string' && lon.trim() != '' ? +lon : NaN;
    this._radius = typeof(rad) == 'number' ? rad : typeof(rad) == 'string' && trim(lon) != '' ? +rad : NaN;
}


/**
 * Returns the distance from this point to the supplied point, in km
 * (using Haversine formula)
 *
 * from: Haversine formula - R. W. Sinnott, "Virtues of the Haversine",
 *       Sky and Telescope, vol 68, no 2, 1984
 *
 * @param   {LatLon} point: Latitude/longitude of destination point
 * @param   {Number} [precision=4]: no of significant digits to use for returned value
 * @returns {Number} Distance in km between this point and destination point
 */
LatLon.prototype.distanceTo = function(point, precision) {
    // default 4 sig figs reflects typical 0.3% accuracy of spherical model
    if (typeof precision == 'undefined') precision = 4;

    var R = this._radius;
    var lat1 = this._lat.toRad(), lon1 = this._lon.toRad();
    var lat2 = point._lat.toRad(), lon2 = point._lon.toRad();
    var dLat = lat2 - lat1;
    var dLon = lon2 - lon1;

    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1) * Math.cos(lat2) *
                    Math.sin(dLon / 2) * Math.sin(dLon / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    var d = R * c;
    return d.toPrecisionFixed(precision);
};
/**
 * Returns the (initial) bearing from this point to the supplied point, in degrees
 *   see http://williams.best.vwh.net/avform.htm#Crs
 *
 * @param   {LatLon} point: Latitude/longitude of destination point
 * @returns {Number} Initial bearing in degrees from North
 */
LatLon.prototype.bearingTo = function(point) {
  var lat1 = this._lat.toRad(), lat2 = point._lat.toRad();
  var dLon = (point._lon-this._lon).toRad();

  var y = Math.sin(dLon) * Math.cos(lat2);
  var x = Math.cos(lat1)*Math.sin(lat2) -
          Math.sin(lat1)*Math.cos(lat2)*Math.cos(dLon);
  var brng = Math.atan2(y, x);

  return (brng.toDeg()+360) % 360;
};
/**
 * Returns the destination point from this point having travelled the given distance (in km) on the
 * given initial bearing (bearing may vary before destination is reached)
 *
 *   see http://williams.best.vwh.net/avform.htm#LL
 *
 * @param   {Number} brng: Initial bearing in degrees
 * @param   {Number} dist: Distance in km
 * @returns {LatLon} Destination point
 */
LatLon.prototype.destinationPoint = function(brng, dist) {
  dist = typeof(dist)=='number' ? dist : typeof(dist)=='string' && dist.trim()!='' ? +dist : NaN;
  dist = dist/this._radius;  // convert dist to angular distance in radians
  brng = brng.toRad();  //
  var lat1 = this._lat.toRad(), lon1 = this._lon.toRad();

  var lat2 = Math.asin( Math.sin(lat1)*Math.cos(dist) +
                        Math.cos(lat1)*Math.sin(dist)*Math.cos(brng) );
  var lon2 = lon1 + Math.atan2(Math.sin(brng)*Math.sin(dist)*Math.cos(lat1),
                               Math.cos(dist)-Math.sin(lat1)*Math.sin(lat2));
  lon2 = (lon2+3*Math.PI) % (2*Math.PI) - Math.PI;  // normalise to -180..+180º

  return new LatLon(lat2.toDeg(), lon2.toDeg());
};

/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */


/**
 * Returns the latitude of this point; signed numeric degrees if no format, otherwise format & dp
 * as per Geo.toLat()
 *
 * @param   {String} [format]: Return value as 'd', 'dm', 'dms'
 * @param   {Number} [dp=0|2|4]: No of decimal places to display
 * @returns {Number|String} Numeric degrees if no format specified, otherwise deg/min/sec
 *
 * @requires Geo
 */
LatLon.prototype.lat = function(format, dp) {
    if (typeof format == 'undefined') return this._lat;

    return Geo.toLat(this._lat, format, dp);
};

/**
 * Returns the longitude of this point; signed numeric degrees if no format, otherwise format & dp
 * as per Geo.toLon()
 *
 * @param   {String} [format]: Return value as 'd', 'dm', 'dms'
 * @param   {Number} [dp=0|2|4]: No of decimal places to display
 * @returns {Number|String} Numeric degrees if no format specified, otherwise deg/min/sec
 *
 * @requires Geo
 */
LatLon.prototype.lon = function(format, dp) {
    if (typeof format == 'undefined') return this._lon;

    return Geo.toLon(this._lon, format, dp);
};

LatLon.prototype.lng = function(format, dp) {
    return this.lon();
};

/**
 * Returns a string representation of this point; format and dp as per lat()/lon()
 *
 * @param   {String} [format]: Return value as 'd', 'dm', 'dms'
 * @param   {Number} [dp=0|2|4]: No of decimal places to display
 * @returns {String} Comma-separated latitude/longitude
 *
 * @requires Geo
 */
LatLon.prototype.toString = function(format, dp) {
    if (typeof format == 'undefined') format = 'dms';

    if (isNaN(this._lat) || isNaN(this._lon)) return '-,-';

    return Geo.toLat(this._lat, format, dp) + ', ' + Geo.toLon(this._lon, format, dp);
};

/* - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  */

// ---- extend Number object with methods for converting degrees/radians

/** Converts numeric degrees to radians */
if (typeof(Number.prototype.toRad) === "undefined") {
    Number.prototype.toRad = function() {
        return this * Math.PI / 180;
    }
}

/** Converts radians to numeric (signed) degrees */
if (typeof(Number.prototype.toDeg) === "undefined") {
    Number.prototype.toDeg = function() {
        return this * 180 / Math.PI;
    }
}

/**
 * Formats the significant digits of a number, using only fixed-point notation (no exponential)
 *
 * @param   {Number} precision: Number of significant digits to appear in the returned string
 * @returns {String} A string representation of number which contains precision significant digits
 */
if (typeof(Number.prototype.toPrecisionFixed) === "undefined") {
    Number.prototype.toPrecisionFixed = function(precision) {
        if (isNaN(this)) return 'NaN';
        var numb = this < 0 ? -this : this;  // can't take log of -ve number...
        var sign = this < 0 ? '-' : '';

        if (numb == 0) {  // can't take log of zero, just format with precision zeros
            var n = '0.';
            while (precision--) n += '0';
            return n
        }

        var scale = Math.ceil(Math.log(numb) * Math.LOG10E);  // no of digits before decimal
        var n = String(Math.round(numb * Math.pow(10, precision - scale)));
        if (scale > 0) {  // add trailing zeros & insert decimal as required
            l = scale - n.length;
            while (l-- > 0) n = n + '0';
            if (scale < n.length) n = n.slice(0, scale) + '.' + n.slice(scale);
        } else {          // prefix decimal and leading zeros if required
            while (scale++ < 0) n = '0' + n;
            n = '0.' + n;
        }
        return sign + n;
    }
}

/** Trims whitespace from string (q.v. blog.stevenlevithan.com/archives/faster-trim-javascript) */
if (typeof(String.prototype.trim) === "undefined") {
    String.prototype.trim = function() {
        return String(this).replace(/^\s\s*/, '').replace(/\s\s*$/, '');
    }
}
