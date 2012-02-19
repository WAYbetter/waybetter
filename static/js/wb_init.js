/**
 *
 * jQuery config
 *
*/

(function ($) {
    $.fn.extend({
        disable:function () {
            return this.each(function () {
                if ($(this).hasClass("ui-button")) {
                    $(this).button("disable");
                } else {
                    $(this).attr({disabled:true});
                }
                if ($.mobile && $(this).is(":button") && !$(this).data("role") === "none") {
                    $(this).button().button("refresh");
                }
            });
        },
        enable:function () {
            return this.each(function () {
                if ($(this).hasClass("ui-button")) {
                    $(this).button("enable");
                } else {
                    $(this).removeAttr('disabled');
                }
                if ($.mobile && $(this).is(":button") && !$(this).data("role") === "none") {
                    $(this).button().button("refresh");
                }
            });
        },
        enabled:function (bool) {
            return this.each(function () {
                if (bool){
                    $(this).enable();
                } else{
                    $(this).disable();
                }
            });
        },
        set_button_text:function (text) {
            return this.each(function () {
                if ($(this).hasClass("ui-button")) {
                    $(this).button("option", "label", text);
                } else {
                    var $inner_span = $(this).parent().find(".ui-btn-text");
                    if ($inner_span.length) {
                        $inner_span.text(text)
                    } else {
                        $(this).text(text);
                    }
                }
            })
        },
        redraw:function () {
            return this.each(function () {
                var element = $(this)[0];
                var current_display = element.style.display;
                element.style.display = 'none';
                element.offsetHeight; // no need to store this anywhere, the reference is enough
                element.style.display = current_display;
                return $(element);
            });
        },
        set_button_theme:function (theme_swatch) {
            var swatch_re = /-(\w)$/;
            return this.each(function () {
                // for jq-mobile
                var parent_element = $(this).closest(".ui-btn");
                if (parent_element.length) {
                    var class_list = parent_element.attr("class").split(/\s+/);
                    var new_class_list = [];
                    $(this).attr("data-theme", theme_swatch);
                    $.each(class_list, function (i, cls) {
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
        swapElement:function (b) {
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
    focus:function (element) {
        return element == document.activeElement;
    }
});

// since django 1.3 CSRF validation applies to AJAX requests
$(document).ajaxSend(function (event, xhr, settings) {
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie != '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = jQuery.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) == (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function sameOrigin(url) {
        // url could be relative or scheme relative or absolute
        var host = document.location.host; // host + port
        var protocol = document.location.protocol;
        var sr_origin = '//' + host;
        var origin = protocol + sr_origin;
        // Allow absolute or scheme relative URLs to same origin
        return (url == origin || url.slice(0, origin.length + 1) == origin + '/') ||
            (url == sr_origin || url.slice(0, sr_origin.length + 1) == sr_origin + '/') ||
            // or any other URL that isn't scheme relative or absolute i.e relative.
            !(/^(\/\/|http:|https:).*/.test(url));
    }

    function safeMethod(method) {
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }

    if (!safeMethod(settings.type) && sameOrigin(settings.url)) {
        xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
    }
});

/**
 *
 * more config
 *
*/

var easydate_config = {
    locale:{
        "future_format":"%s %t",
        "past_format":"%s %t",
        "second":"שנייה",
        "seconds":"שניות",
        "minute":"דקה",
        "minutes":"דקות",
        "hour":"שעה",
        "hours":"שעות",
        "day":"יום",
        "days":"ימים",
        "week":"שבוע",
        "weeks":"שבועות",
        "month":"חודש",
        "months":"חודשים",
        "year":"שנה",
        "years":"שנים",
        "yesterday":"אתמול",
        "tomorrow":"מחר",
        "now":"כעת",
        "ago":"לפני",
        "in":"בעוד"
    },
    units:[
        { name:"now", limit:59 },
        { name:"minute", limit:3600, in_seconds:60 },
        { name:"hour", limit:86400, in_seconds:3600  },
        { name:"yesterday", limit:172800, past_only:true },
        { name:"tomorrow", limit:172800, future_only:true },
        { name:"day", limit:604800, in_seconds:86400 },
        { name:"week", limit:2629743, in_seconds:604800  },
        { name:"month", limit:31556926, in_seconds:2629743 },
        { name:"year", limit:Infinity, in_seconds:31556926 }
    ]
};
