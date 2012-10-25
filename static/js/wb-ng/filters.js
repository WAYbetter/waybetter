var module = angular.module('wbFilters', []);

module.filter('range', function() {
  return function(input, total) {
    total = parseInt(total);
    for (var i=0; i<total; i++)
      input.push(i);
    return input;
  };
});

module.filter('zero_padding', function () {
    return function (input, length) {
        if (input == undefined) {
            return input;
        }

        var string_input = String(input);
        var out = string_input;
        for (var i = 0; i < length - string_input.length; i++) {
            out = "0" + out;
        }

        return out;
    }
});
module.filter('paren_wrap', function () {
    return function (input, length) {
        if (input == undefined) {
            return input;
        }

        return "(" + input + ")";
    }
});

module.filter('wb_date', function ($filter) {
    return function(date, format) {
        var now = new Date();
        date = new Date(date);

        // replace EEE d/M with "Today" if date is today
        // TODO: handle "EEEE" and multiple occurrences
        if (now.toDateString() == date.toDateString()) {
            var day_format = "EEE";
            var idx = format.indexOf(day_format);

            if (idx > -1) {
                format = format.replace("d/M", "");
                var pre = "", post = "";
                if (format.substring(0, idx) != "") {
                    pre = $filter('date')(date, format.substring(0, idx));
                }
                if (format.substring(idx + day_format.length) != "") {
                    post = $filter('date')(date, format.substring(idx + day_format.length));
                }
                return pre + "היום" + post;
            }
        }
        return $filter('date')(date, format)
    }
});