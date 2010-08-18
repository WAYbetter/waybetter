{% load i18n %}

function openSignupDialog() {
    $('#dialog-form').dialog('open');
}

    var username = $("<input>").attr('name', 'username'),
        email = $("<input>").attr('name', 'email').addClass('required'),
        password = $("<input>").attr('name', 'password').attr('type', 'password').attr('id', 'password'),
        password_again = $("<input>").attr('name', 'password_again').attr('type', 'password'),
        local_phone = $("<input>").attr('name', 'local_phone'),
        verification_code = $("<input>").attr('name', 'verification_code'),
        allFields = $([]).add(username).add(email).add(password).add(password_again),
        tips = $("<div></div>").addClass("validateTips");

    var country = $("<select name='country'></select>");
    {% for country in countries %}
    country.append($("<option>").val('{{ country.id }}').append("{{ country.name|truncatewords:3 }} ({{ country.dial_code }})"));
    {% endfor %}


    var user_details_table =
        $("<table></table>")
            .append($("<tr></tr>")
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'username').append("{% trans 'Username' %}"))
                    .append(username))
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'email').append("{% trans 'Email' %}"))
                    .append(email)))
            .append($("<tr></tr>")
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'password').append("{% trans 'Password' %}"))
                    .append(password))
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'password_again').append("{% trans 'Re-enter Password' %}"))
                    .append(password_again)));

    var user_details_form = $("<form></form>").append(user_details_table);
    var user_details_validator = user_details_form.validate({
        errorClass: 'ui-state-error', 
        rules: {
            username: "required",
            email: "email",
            password: "required",
            password_again: {
                required: true, 
                equalTo: "#password"
            }
        }
    });

    var send_sms_button = $("<button></button>").append("{% trans 'Send SMS verification code' %}").button().click(sendSMSVerification);


    var phone_verification_table =
        $("<table></table>")
            .append($("<tr></tr>")
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'country').append("{% trans 'Country' %}"))
                    .append(country)))
            .append($("<tr></tr>")
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'local_phone').append("{% trans 'Local Phone' %}"))
                    .append(local_phone)))
            .append($("<tr></tr>")
                .append($("<td></td>")
                    .append(send_sms_button)))
            .append($("<tr></tr>")
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'verification_code').append("{% trans 'Enter SMS Code' %}"))
                    .append(verification_code)));

        var user_details = $("<div></div>").append(user_details_form);
        var phone_verification = $("<div></div>").hide().append(phone_verification_table);

        $("<div></div>").attr('id', "dialog-form").appendTo("body");
        $("#dialog-form").append(tips).append(user_details).append(phone_verification);
        $('#dialog-form').dialog({
            autoOpen: false,
            height: 300,
            width: 350,
            modal: true,
            title: "{% trans 'Sign up using the following details'  %}",
            buttons: {
            '{% trans "Continue" %}': function() {}
            },
            open: initDialog
        });

        openSignupDialog();
        $("label").css("display", "block");


    function initDialog(event, ui) {
        var dialog_button = $(".ui-dialog-buttonset button");
        dialog_button.button("enable");
        dialog_button.button("option", "label", "{% trans 'Continue' %}");
        dialog_button.click(function() {
            doContinue();
        });
        phone_verification.hide();
        user_details.show();
    }

    function doContinue() {
        console.log("doContinue");
        var is_valid = validateUserInfo();
        if (is_valid) {
            $("#dialog-form").dialog("option", "title", "{% trans 'Fill in to finish registration' %}");
            $(".ui-dialog-buttonset button").button("disable");
            $(".ui-dialog-buttonset button").button("option", "label", "{% trans 'Finish' %}");
            user_details.hide();
            phone_verification.show();
        }
    }
    function validateUserInfo() {
        console.log("validateUserInfo");
        return user_details_validator.form();
//        var result = true;
//        tips.empty();
//        allFields.removeClass('ui-state-error');
//        var temp_result = checkLength(email,"email",6,80);
//        result = result && temp_result;
//        temp_result = checkLength(username,"username",3,16);
//        result = result && temp_result
//        temp_result = checkLength(password,"password",5,16);
//        result = result && temp_result
//
//
//        if (tips.text()) {
//            tips.effect("highlight", {}, 1500);
//        }
//        return result;
    }

    function updateTips(t) {
        tips.append(t);
        tips.append("<br>");
    }

    function checkLength(o,n,min,max) {
        console.log("in checkLength for " + n);
        if ( o.val().length > max || o.val().length < min ) {
            o.addClass('ui-state-error');
            updateTips("Length of " + n + " must be between "+min+" and "+max+".");
            return false;
        } else {
            return true;
        }
    }

    function checkRegexp(o,regexp,msg) {
        if ( !( regexp.test( o.val() ) ) ) {
            o.addClass('ui-state-error');
            updateTips(msg);
            return false;
        } else {
            return true;
        }
    }

    function sendSMSVerification() {
        alert('the SMS is on the way (not...)');
    }

 //		$("#dialog-form").dialog({
//			autoOpen: false,
//			height: 300,
//			width: 350,
//			modal: true,
//			buttons: {
//				'Create an account': function() {
//					var bValid = true;
//					allFields.removeClass('ui-state-error');
//
//					bValid = bValid && checkLength(name,"username",3,16);
//					bValid = bValid && checkLength(email,"email",6,80);
//					bValid = bValid && checkLength(password,"password",5,16);
//
//					bValid = bValid && checkRegexp(name,/^[a-z]([0-9a-z_])+$/i,"Username may consist of a-z, 0-9, underscores, begin with a letter.");
//					// From jquery.validate.js (by joern), contributed by Scott Gonzalez: http://projects.scottsplayground.com/email_address_validation/
//					bValid = bValid && checkRegexp(email,/^((([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+(\.([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+)*)|((\x22)((((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(([\x01-\x08\x0b\x0c\x0e-\x1f\x7f]|\x21|[\x23-\x5b]|[\x5d-\x7e]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(\\([\x01-\x09\x0b\x0c\x0d-\x7f]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]))))*(((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(\x22)))@((([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.)+(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.?$/i,"eg. ui@jquery.com");
//					bValid = bValid && checkRegexp(password,/^([0-9a-zA-Z])+$/,"Password field only allow : a-z 0-9");
//
//					if (bValid) {
//						$('#users tbody').append('<tr>' +
//							'<td>' + name.val() + '</td>' +
//							'<td>' + email.val() + '</td>' +
//							'<td>' + password.val() + '</td>' +
//							'</tr>');
//						$(this).dialog('close');
//					}
//				},
//				Cancel: function() {
//					$(this).dialog('close');
//				}
//			},
//			close: function() {
//				allFields.val('').removeClass('ui-state-error');
//			}
//		});

