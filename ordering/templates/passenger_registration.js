{% load i18n %}
var onRegisterSuccess;
function openSignupDialog() {
    $('#dialog-form').dialog('open');
}

$(document).ready(function() {

    var username = $("<input>").attr('name', 'username'),
        email = $("<input>").attr('name', 'email'),
        password = $("<input>").attr('name', 'password').attr('type', 'password').attr('id', 'password'),
        password_again = $("<input>").attr('name', 'password_again').attr('type', 'password'),

        local_phone = $("<input>").attr('name', 'local_phone').attr('id', 'local_phone').keyup(function() {
            if ($(this).val()) {
                send_sms_button.button("enable");
            } else{
                send_sms_button.button("disable");
            }
        }),
        verification_code = $("<input>").attr('name', 'verification_code').attr('disabled', 'disabled').keyup(function() {
            if ($(this).val()) {
                $(".ui-dialog-buttonset button").button("enable")
            } else {
                $(".ui-dialog-buttonset button").button("disable")
            }
        });

    var country = $("<select name='country'></select>");
    {% for country in countries %}
    country.append($("<option>").val('{{ country.id }}').append("{{ country.name|truncatewords:3 }} ({{ country.dial_code }})"));
    {% endfor %}

    var allFields = [username, email, password, country, local_phone, verification_code];

    var send_sms_button = $("<button></button>").append("{% trans 'Send SMS verification code' %}").button();
    send_sms_button.button("disable");
    send_sms_button.unbind("click");
    send_sms_button.click(sendSMSVerification);

    var progress_indicator = $("<img>").attr("src", "/static/img/indicator_small.gif").css("display", "inline").hide();

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
            email: {
                required: true,
                email: true
            },
            password: "required",
            password_again: {
                required: true, 
                equalTo: "#password"
            }
        }
    });

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
                    .append(send_sms_button).append(progress_indicator)))
            .append($("<tr></tr>")
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'verification_code').append("{% trans 'Enter SMS Code' %}"))
                    .append(verification_code)));

        var phone_verification_form = $("<form></form").append(phone_verification_table);
        var phone_verification_validator = phone_verification_form.validate({
            errorClass: 'ui-state-error',
            rules: {
                verification_code: "required",
                local_phone: {
                    required: true,
                    digits: true
                }
            }
        });

        var user_details = $("<div></div>").append(user_details_form);


        var phone_verification = $("<div></div>").hide().append(phone_verification_form);

        $("<div></div>").attr('id', "dialog-form").appendTo("body");
        $("#dialog-form").append(user_details).append(phone_verification);
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

//        openSignupDialog();
        $("label").css("display", "block");


    function initDialog(event, ui) {
        var dialog_button = $(".ui-dialog-buttonset button");
        dialog_button.button("enable");
        dialog_button.button("option", "label", "{% trans 'Continue' %}");
        dialog_button.unbind("click");
        dialog_button.click(function() {
            doContinue();
        });
        phone_verification.hide();
        user_details.show();
    }

    function doContinue() {
        var is_valid = user_details_validator.form();
        if (is_valid) {
            $("#dialog-form").dialog("option", "title", "{% trans 'Fill in to finish registration' %}");
            var dialog_button = $(".ui-dialog-buttonset button");
            dialog_button.button("disable");
            dialog_button.button("option", "label", "{% trans 'Finish' %}");
            dialog_button.unbind("click");
            dialog_button.click(function() {
               doSubmit(); 
            });
            user_details.hide();
            phone_verification.show();
        }
    }

    function doSubmit() {
         var is_valid = phone_verification_validator.form();

        if (is_valid) {
            var data = {};
            for (var i in allFields) {
                var input = $(allFields[i]);
                data[input.attr("name")] = input.val();
            }
            $.ajax({
                url: "{% url ordering.passenger_controller.register_passenger %}",
                type: "post",
                data: data,
                success: function(data) {
                    $('#dialog-form').dialog("close");
                    if (onRegisterSuccess) {
                        onRegisterSuccess.call();
                    }
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    alert('error: ' + XMLHttpRequest.responseText);
                }
            });
        }
    }
   

    function sendSMSVerification() {
        if (phone_verification_validator.element("#local_phone")) {
            progress_indicator.show();
            $.post("{% url ordering.passenger_controller.send_sms_verification %}", { phone: local_phone.val() }, function(data) {
                progress_indicator.hide();
                alert('code:' + data);
                send_sms_button.button("disable");
                verification_code.attr("disabled", "");
            });
        }
        return false;
    }
});


