function isNumber(n) {
  return !isNaN(parseFloat(n)) && isFinite(n);
}
function get_address_component(place, type_name) {
    var cmpnt = undefined;

    angular.forEach(place.address_components, function (component) {
        if (component.types && component.types.indexOf(type_name) > -1) {
            cmpnt = component;
        }
    });

    return cmpnt;
}
function Address() {
    this.street = undefined;
    this.house_number = undefined;
    this.city_name = undefined;
    this.country_code = undefined;
    this.lat = undefined;
    this.lng = undefined;
}
Address.prototype = {
    isValid: function () {
        return !!(this.lat && this.lng && this.street && isNumber(this.house_number))
    },
    formatted_address: function() {
        return this.street + " " + this.house_number + ", " + this.city_name;
    }
};

Address.fromPlace = function (place) {
    function _get_component_value(type) {
        var res = undefined;
        if (!place.address_components) {
            return res
        }

        angular.forEach(place.address_components, function (component) {
            if (component.types && $.inArray(type, component.types) > -1) {
                res = component.short_name;
            }
        });

        return res;
    }

    var address = new Address();

    address.lat = place.geometry.location.lat();
    address.lng = place.geometry.location.lng();

    address.street = _get_component_value("route");
    address.house_number = _get_component_value("street_number");
    address.city_name = _get_component_value("locality");
    address.country_code = _get_component_value("country");


    return address
};
Address.fromJSON = function (json) {
    var obj = angular.fromJson(json);
    var address = new Address();

    address.street = obj.street;
    address.house_number = obj.house_number;
    address.city_name = obj.city_name;
    address.country_code = obj.country_code;
    address.lat = obj.lat;
    address.lng = obj.lng;

    return address
};



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
