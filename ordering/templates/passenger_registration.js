{% load i18n %}
var onRegisterSuccess;
var loginState = {
    init: function(self) {
        self.dialog.empty();
        self.username = $("<input>").attr('name', 'username');
        self.password = $("<input>").attr('name', 'password').attr('type', 'password').attr('id', 'password')
        self.allFields = [self.username, self.password];
        self.user_login_table =
            $("<table></table>")
                .append($("<tr></tr>")
                    .append($("<td></td>")
                        .append($("<label></label>").attr('for', 'username').append("{% trans 'Username' %}"))
                        .append(self.username))
                    .append($("<td></td>")
                        .append($("<label></label>").attr('for', 'password').append("{% trans 'Password' %}"))
                        .append(self.password)));

        self.user_login_form = $("<form></form>").append(self.user_login_table).submit(function(){ return false });
        self.user_login_validator = self.user_login_form.validate({
            errorClass: 'my-ui-state-error',
            rules: {
                username: "required",
                password: "required"
            }
        });
        self.registration_link = $("<span></span>").addClass("link").text("{% trans "Don't have an account?" %}").click(function() { self.registerMode(self) });

        var twitter_link = $("<a></a>").attr('id', 'twitter_login_link').addClass('openid_large_btn twitter').attr('href', "{% url socialauth_twitter_login %}?next={{ next }}");

        var input1 = $("<input>").attr('id', 'openid_identifier').attr('name', 'openid_identifier').attr('type', 'text');
        self.openid_container = $("<div></div>")
                .append($("<div></div>").attr('id', 'openid_choice').append($("<div></div>").attr('id', 'openid_btns').append(twitter_link)))
                .append($("<input>").attr('name', 'openid_next').attr('type', 'hidden'))
                .append($("<div></div>").attr('id', 'openid_input_areas'));
        self.openid_form = $("<form></form>").attr('action', "{% url socialauth_openid_login %}").attr('method', 'get').attr('id', 'openid_form')
                .append($("<input>").attr('type', 'hidden').attr('name', 'action').val('verify'));
        self.openid_form.append(self.openid_container);


        self.login = $("<div></div>").append(self.user_login_form).append(self.registration_link).append(self.openid_form);
        self.dialog.append(self.login);
        twitter_link.wrap("<div id='twitter'></div>");
    },
    doLogin:function(self) {
        var is_valid = self.user_login_validator.form();

        if (is_valid) {
            var data = {};
            for (var i in self.allFields) {
                var input = $(self.allFields[i]);
                data[input.attr("name")] = input.val();
            }
            $.ajax({
                url: "{% url ordering.passenger_controller.login_passenger %}",
                type: "post",
                data: data,
                success: function(data) {
                    self.dialog.dialog("close");
                    if (onRegisterSuccess) {
                        onRegisterSuccess.call();
                    }
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    alert('error: ' + XMLHttpRequest.responseText);
                }
            });
        }
    },
    registerMode: function(self) {
        registerState.buildDialog(self.dialog);
    },
    dialogSettings: {
        autoOpen: false,
        modal: true,
        title: "{% trans 'Login using the following details' %}",
        width: 350,
        height: 200,
        buttons: {
            "{% trans 'Login' %}": function() { loginState.doLogin(loginState) },
        },
        open: function() {  }

    },
    buildDialog: function(container) {
        this.dialog = $(container).dialog(this.dialogSettings);
        this.init(this);
        return this;
        
    }
}


// --------------------===================================-------------------------------===============================
// --------------------===================================-------------------------------===============================
// --------------------===================================-------------------------------===============================
// --------------------===================================-------------------------------===============================



var registerState = {
    init: function(self) {
        self.dialog.empty();
        
        self.username = $("<input>").attr('name', 'username');
        self.email = $("<input>").attr('name', 'email');
        self.password = $("<input>").attr('name', 'password').attr('type', 'password').attr('id', 'password')
        self.password_again = $("<input>").attr('name', 'password_again').attr('type', 'password');

        self.local_phone = $("<input>").attr('name', 'local_phone').attr('id', 'local_phone').keyup(function() {
            if ($(this).val()) {
                self.send_sms_button.button("enable");
            } else{
                self.send_sms_button.button("disable");
            }
        });
        self.verification_code = $("<input>").attr('name', 'verification_code').attr('disabled', 'disabled').keyup(function() {
            if ($(this).val()) {
                $(".ui-dialog-buttonset button").button("enable")
            } else {
                $(".ui-dialog-buttonset button").button("disable")
            }
        });

        self.country = $("<select name='country'></select>");
        {% for country in countries %}
        self.country.append($("<option>").val('{{ country.id }}').append("{{ country.name|truncatewords:3 }} ({{ country.dial_code }})"));
        {% endfor %}

        self.allFields = [self.username, self.email, self.password, self.country, self.local_phone, self.verification_code];

        self.send_sms_button = $("<button></button>").append("{% trans 'Send SMS verification code' %}").button();
        self.send_sms_button.button("disable");
        self.send_sms_button.unbind("click");
        self.send_sms_button.click(function() {
            self.sendSMSVerification(self);
        });
        

        self.progress_indicator = $("<img>").attr("src", "/static/images/indicator_small.gif").css("display", "inline").hide();

        self.user_details_table =
        $("<table></table>")
            .append($("<tr></tr>")
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'username').append("{% trans 'Username' %}"))
                    .append(self.username))
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'email').append("{% trans 'Email' %}"))
                    .append(self.email)))
            .append($("<tr></tr>")
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'password').append("{% trans 'Password' %}"))
                    .append(self.password))
                .append($("<td></td>")
                    .append($("<label></label>").attr('for', 'password_again').append("{% trans 'Re-enter Password' %}"))
                    .append(self.password_again)));


        self.user_details_form = $("<form></form>").append(self.user_details_table).submit(function(){ return false });
        self.user_details_validator = self.user_details_form.validate({
            errorClass: 'my-ui-state-error',
            rules: {
                username: {
                    required: true,
                    remote: "{% url common.services.is_username_available %}"
                },
                email: {
                    required: true,
                    email: true
                },
                password: "required",
                password_again: {
                    required: true,
                    equalTo: "#password"
                }
            },
            messages: {
                username: {
                    remote: "{% trans 'The username is already taken' %}"
                }
            }
        });

        self.phone_verification_table =
            $("<table></table>")
                .append($("<tr></tr>")
                    .append($("<td></td>")
                        .append($("<label></label>").attr('for', 'country').append("{% trans 'Country' %}"))
                        .append(self.country)))
                .append($("<tr></tr>")
                    .append($("<td></td>")
                        .append($("<label></label>").attr('for', 'local_phone').append("{% trans 'Local Phone' %}"))
                        .append(self.local_phone)))
                .append($("<tr></tr>")
                    .append($("<td></td>")
                        .append(self.send_sms_button).append(self.progress_indicator)))
                .append($("<tr></tr>")
                    .append($("<td></td>")
                        .append($("<label></label>").attr('for', 'verification_code').append("{% trans 'Enter SMS Code' %}"))
                        .append(self.verification_code)));

        self.phone_verification_form = $("<form></form>").append(self.phone_verification_table).submit(function(){ return false });
        self.phone_verification_validator = self.phone_verification_form.validate({
            errorClass: 'ui-state-error',
            rules: {
                verification_code: {
                    required: true,
                    digits: true,
                    minlength: 4,
                    maxlength: 4
                },
                local_phone: {
                    required: true,
                    digits: true
                }
            }
        });

        self.login_link = $("<span></span>").addClass("link").text("{% trans 'Already have an account?' %}").click(function() { self.loginMode(self) });
        self.user_details = $("<div></div>").append(self.user_details_form).append(self.login_link);
        self.phone_verification = $("<div></div>").hide().append(self.phone_verification_form);


        self.dialog.append(self.user_details).append(self.phone_verification);

//        openSignupDialog();
    },
    doContinue: function(self) {
        var is_valid = self.user_details_validator.form();
        if (is_valid) {
            self.phoneVerification(self);
        }
    },
    doSubmit: function(self) {
         var is_valid = self.phone_verification_validator.form();

        if (is_valid) {
            var data = {};
            for (var i in self.allFields) {
                var input = $(self.allFields[i]);
                data[input.attr("name")] = input.val();
            }
            $.ajax({
                url: "{% url ordering.passenger_controller.register_passenger %}",
                type: "post",
                data: data,
                success: function(data) {
                    self.dialog.dialog("close");
                    if (onRegisterSuccess) {
                        onRegisterSuccess.call();
                    }
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    alert('error: ' + XMLHttpRequest.responseText);
                }
            });
        }
    },
    phoneVerification: function(self) {
        self.dialog.dialog("option", "title", "{% trans 'Fill in to finish registration' %}");
        var dialog_button = $(".ui-dialog-buttonset button");
        dialog_button.button("disable");
        dialog_button.button("option", "label", "{% trans 'Finish' %}");
        dialog_button.unbind("click");
        dialog_button.click(function() {
            self.doSubmit(self);
        });
        self.user_details.hide();
        self.phone_verification.show();
    },
    sendSMSVerification: function (self) {
        if (self.phone_verification_validator.element("#local_phone")) {
            self.progress_indicator.show();
            $.post("{% url ordering.passenger_controller.send_sms_verification %}", { phone: self.local_phone.val() }, function(data) {
                self.progress_indicator.hide();
                alert('verification code:' + data);
                self.send_sms_button.button("disable");
                self.verification_code.attr("disabled", "").focus();

            });
        }
        return false;
    },
    loginMode: function(self) {
        loginState.buildDialog(self.dialog);
    },
    dialogSettings: {
        autoOpen: false,
        title: "{% trans 'Sign up using the following details'  %}",
        width: 350,
        height: 300,
        buttons: {
            "{% trans 'Continue' %}": function () { registerState.doContinue(registerState) }
        },
        open: function () { registerState.init(registerState) }
    },
    buildDialog: function(container) {
        this.dialog = $(container).dialog(this.dialogSettings);
        this.init(this);
    }
};


function openSignupDialog(callback, showPhoneVerificationOnly) {
    if (callback) {
        onRegisterSuccess = callback;
    }
    $('#dialog-form').dialog('open');

    if (showPhoneVerificationOnly) {
        registerState.buildDialog($('#dialog-form'));
        registerState.phoneVerification(registerState);
    }
}

$(document).ready(function() {
    var container = $("<div></div>").attr('id', "dialog-form").appendTo("body").hide();
    loginState.buildDialog(container);
    openid.init('openid_identifier');
});
        