var Registrator = Object.create({
    default_config           : {
        urls            : {
            error_form_template             : '/',
            login_form_template             : '/',
            reg_form_template               : '/',
            credentials_form_template       : '/',
            phone_form_template             : '/',
            cant_login_form_template        : '/',
            phone_code_form_template        : '/',
            feedback_form_template          : '/',
            sending_form_template           : '/',
            terms_form_template             : '/',
            mobile_interest_form_template   : '/',
            station_interest_form_template  : '/',
            business_interest_form_template : '/',
            check_email                     : '/',
            login                           : '/',
            send_sms                        : '/',
            update_profile                  : '/',
            register                        : '/',
            change_credentials              : '/',
            validate_phone                  : '/'
        },
        dialog_config   : {
            autoOpen: false,
            resizable: false,
            modal: true,
            width: 500,
            position: ["center", 100],
            draggable: false,
            zIndex:2000
        },
        error_messages  : {
            invalid_email           : ''
        },
        messages        : {
            enter_email             : '',
            choose_password         : '',
            valid_field             : '',
            code_sent               : '',
            sending_code            : '',
            finish                  : '',
            sms_ok                  : '',
            interest_submitted_dialog_title_html: '',
            interest_submitted_dialog_content_html: ''
        },
        current_dialog_is_sending   : false,
        callback        : function () {}
    },
    validator               : undefined,
    default_validator_config: {
        errorClass: 'ui-state-error',
        errorElement: 'span',
        focusCleanup: true,
        ui_functions: {
            highlight: function(element, errorClass, validClass) {
                Registrator.highlight.call(Registrator, element, errorClass, validClass)
            },
            unhighlight: function(element, errorClass, validClass) {
                Registrator.unhighlight.call(Registrator, element, errorClass, validClass)
            },
            errorPlacement: function(error, element) {
                Registrator.errorPlacement.call(Registrator, error, element)
            },
            success: function(label) { Registrator.success.call(Registrator, label) }
        }
    },
    config                  : {},
    /**
     * Initializes this.config
     *
     * @param config
     * @return this
     */
    init                    : function (config, open_login_dialog) {
        // config will be the argument config
        // OR the global var 'form_config' provided in the template

        var _config = window.form_config ? form_config : {};
        config = config || _config;

        this.config = $.extend(true, {}, this.default_config, this.config, config);
        if (! $("#dialog").length) {
            $("<div id='dialog'></div>").hide().appendTo("body");
        }
        $("#dialog").dialog(this.config.dialog_config);
        if (open_login_dialog){
            this.openLoginDialog(function(){
                        window.location.href = "/";
                    });
        }
        return this;
    },
    initValidator           : function ($form, config) {
        var _config = $.extend(true, {}, this.default_validator_config, config);
        this.validator = $form.validate(_config);
        return this;
    },
    isSending               : function() {
        return this.config.current_dialog_is_sending;
    },
    setCallback             : function (callback) {
        if ( callback && $.isFunction(callback) ) {
            this.config.callback = callback;
        }
        return this;
    },
    /**
     * Gets the form template using AJAX by template_name as prefix
     * on success fires the given callback
     * with the dialog content as argument
     *
     * @param template_name
     * @param callback
     * @return callback($dialog_content)
     */
    getTemplate             : function (template_name, callback) {
        var that = this;
        $.ajax({
            url : this.config.urls[template_name+'_form_template'],
            type : 'get',
            success : function (template) {
                // inject the form into the DOM
                var dialog = $('#dialog').empty().append(template);
                // we probably have a new form_config object
                that.init.call(that);
                return callback(dialog);
            }
        });
    },
    doLogin                 : function (form) {
        this._doDialogSubmit(form, null, this.config.urls.login, function(XMLHttpRequest, textStatus, errorThrown) {
            $("#login_error", form).text(XMLHttpRequest.responseText);
        });
    },
    _doDialogSubmit          : function (form, extra_form_data, url, errorCallback, successCallback) {
        var that = this,
            data = extra_form_data ? extra_form_data + '&' + $(form).serialize() : $(form).serialize(),
            error = errorCallback ? errorCallback : function (XMLHttpRequest, textStatus, errorThrown) {
                    alert(XMLHttpRequest.responseText);
            },
            success = successCallback ? successCallback : function(response) {
                $('#dialog').dialog('close');
                if ( that.config.callback ) {
                    that.config.callback(response);
                }
            };

        if (!this.validator || (!this.validator.form || this.validator.form())) {
            $.ajax({
                url :url,
                type : 'post',
                data : data,
                success : success,
                error   : error
            });
        }
    },
    doFeedback              : function(form) {
        this._doDialogSubmit(form, undefined, this.config.urls.feedback_form_template, undefined, function(response) {
            $("#sent_message").fadeIn("fast");
        });
    },
    doProfileUpdate         : function(form, extra_form_data) {
        this._doDialogSubmit(form, extra_form_data, this.config.urls.update_profile);
    },
    doPhoneValidation       : function(form) {
        this._doDialogSubmit(form, null, this.config.urls.validate_phone, function(XMLHttpRequest, textStatus, errorThrown) {
            $("div[htmlfor=verification_code]").text(XMLHttpRequest.responseText).parent()
                    .removeClass("sms-button").addClass("red").unbind("click");
        });
    },
    doRegister              : function (form, extra_form_data) {
        this._doDialogSubmit(form, extra_form_data, this.config.urls.register);
    },
    doChangeCredentials     : function (form, extra_form_data) {
        this._doDialogSubmit(form, extra_form_data, this.config.urls.change_credentials);
    },
    doSubmitInterest        : function(form, url) {
        this._doDialogSubmit(form, undefined, url, undefined, function(response) {
            if (! response.errors) {   // no errors!
                $("#dialog").dialog("close");
                openDialog(Registrator.config.messages.interest_submitted_dialog_title_html,
                            Registrator.config.messages.interest_submitted_dialog_content_html, undefined);
            } else {                    // we got errors
                $.each(response.errors, function(i, error) {
                    for (var field_name in error) {
                        var $errors = $("<ul class='errorlist'></ul>").hide();
                        $.each(error[field_name], function(i, val) {
                            $errors.append($("<li></li>").text(val));
                        });
                        $("input[name=" + field_name + "]").before($errors);
                        $errors.fadeIn('fast');
                    }
                });
            }
        });
    },
    openErrorDialog         : function(title, message, callback) {
        var that = this;
        this.setCallback(callback);
        this.getTemplate.call(this, 'error', function (dialog_content) {
            $("#content", dialog_content).html(message);
            $("#ok").click(function () {
                $("#dialog").dialog("close");    
            });
            that.openDialog.call(that, {}, { "title": title });
        });
    },
    openFeedbackDialog      : function (callback) {
        var that = this;
        that.setCallback(callback);
        that.getTemplate.call(that, 'feedback', function(dialog_content) {
            var form = $("form", dialog_content);
            $("#sent_message", dialog_content).hide();
            $("#close", dialog_content).click(function() {
                $('#dialog').dialog('close');
            });
            $("#submit_feedback", dialog_content).click(function() {
                that.doFeedback(form);
            });
            that.openDialog.call(that);
        });
    },
    _openInterestDialog: function (interest_name, callback, dialog_setup_callback) {
        var that = this;
        that.setCallback(callback);
        that.getTemplate.call(that, interest_name+"_interest", function(dialog_content) {
            var form = $("form", dialog_content);
            $("#close", dialog_content).click(function() {
                $('#dialog').dialog('close');
            });
            if (dialog_setup_callback) {
                dialog_setup_callback.call();
            }
            that.openDialog.call(that);
        });
    },
    openMobileInterestDialog: function (callback) {
        this._openInterestDialog.call(this, "mobile", callback);
    },
    openStationInterestDialog: function (callback) {
        this._openInterestDialog.call(this, "station", callback);
    },
    openBusinessInterestDialog: function(callback, dialog_setup_callback){
        this._openInterestDialog.call(this, "business", callback, dialog_setup_callback);
    },
    openTermsDialog         : function (callback) {
        var that = this;
        that.setCallback(callback);
        that.getTemplate.call(that, 'terms', function(dialog_content) {
            $("#ok", dialog_content).click(function() {
                $("#dialog").dialog('close');
            });
            that.openDialog.call(that);
        });
    },
    openLoginDialog         : function (callback) {
        var that = this;
        this.setCallback(callback);
        this.getTemplate.call(this, 'login', function (dialog_content) {
            var validation_config = {
                errorClass  : "inputError",
                validClass  : "inputValid",
                focusCleanup: false,
                errorElement: "div",
                highlight: function(element, errorClass, validClass) {
                    $(element).next().addClass(errorClass).removeClass(validClass).removeClass("red").removeClass("green");
                    for (var key in that.config.error_messages) {
                        if (that.config.error_messages[key] === this.errorList[0].message) {
                            $(element).next().addClass("red");
                        }
                    }
                },
                unhighlight: function(element, errorClass, validClass) {
                    $(element).next().addClass(validClass).removeClass(errorClass);
                },
                errorPlacement: function(error, element) {
                    var container = $("<div></div>").addClass("input-helper");
                    container.append(error);
                    container.insertAfter(element);
                },
                success: function (label) {
                    label.text(that.config.messages.valid_field).parent().removeClass("red").addClass("green");
                },
                rules: {
                    username: {
                        required: true
                        //email: true
                    },
                    password: "required"
                },
                messages: {
                    username: {
                        required: that.config.messages.enter_email,
                        email   : that.config.error_messages.invalid_email
                    },
                    password: {
                        required: that.config.messages.choose_password
                    }
                }
            },
            // something is binding click to form submit here, must unbind
            $button = $('#login', dialog_content).unbind('click').bind('click', function (e) {
                    that.doLogin.call(that, this.form);
                    e.preventDefault();
                    return false;
            }),
            $show_register_link = $('#show_register')
                .unbind('click')
                .bind('click', function (e) {
                    that.doJoin();
                    return false;
            });
            that.openDialog.call(that, validation_config);
        });
    },
    _openPhoneDialog         : function (extra_form_data, while_ordering, template) {
        var that = this;

        var template_name = (template) ? template : "phone";

        // add custom validation method
        $.validator.addMethod('ignoreNonDigits', function(val, elem) {
            var new_val = val.split(/\D+/).join("");
            if (new_val != val) {
                jQuery(elem).val(new_val);
            }
            return $.validator.methods.required.call(this, new_val, elem);
        });

        this.getTemplate.call(this, template_name, function (dialog_content) {
            var $finish_button = $('form input#validate', dialog_content).button()
               .unbind('click')
               .bind('click', function (e) {
                    that.doPhoneValidation.call(that, this.form, extra_form_data);
                    return false;
            }),
            $phone_input = $('form input#local_phone', dialog_content).focus(function() {
                $(this).next().removeClass("code-sent");
            }).keyup(function(e) {
                if (e.keyCode == '13') {
                    $(this).next().mouseup();
                }
            }),
            $verification_code_input = $('form input#verification_code', dialog_content)
                .unbind('keyup')
                .bind('keyup', function(e) {
                    if (that.validator.element($verification_code_input)) {
                        $finish_button.button("enable");
                    } else {
                        $finish_button.button("disable");
                    }
                    if (e.keyCode == '13') {
                        $(this).next().mouseup();
                    }
            }),
            validation_config = window.validation_config,
            more_validation_config =  {
                errorPlacement: function(error, element) {
                    var container = $("<div></div>").addClass("input-helper");
                    container.append(error);
                    container.insertAfter(element);
                },
                success: function(label) {
                    if (label.attr("htmlfor") == 'local_phone') {
                        label.text(that.config.messages.sms_ok);
                    } else {
                        label.text(that.config.messages.finish);
                    }
                },
                showErrors: function(errorMap, errorList) {
                    var form = $("form", dialog_content)[0];
                    that.setHelperButton(this, 'local_phone', function() {
                        that.sendSMS.call(that, form, $('#verification_code', dialog_content));
                    });

                    that.setHelperButton(this, 'verification_code', function() {
                        $("div[htmlfor=local_phone]").parent().removeClass("code-sent");
                        that.doPhoneValidation.call(that, form, extra_form_data);
                    });

                    this.defaultShowErrors();
                }
            };
            $.extend(validation_config, that.default_validator_config.ui_functions, more_validation_config);


            $(".login_link").live("mouseup", function() {
                if (!while_ordering){
                    that.setCallback(function(){
                        window.location.href = "/";
                    });
                }
                that.openLoginDialog();
                return false;
            });
            that.openDialog.call(that, validation_config);
            $phone_input.focus();
        });
    },
    openPhoneDialog         : function (callback) {
        this.setCallback(callback);
        this._openPhoneDialog();
        return this;
    },
    openPhoneDialogWhileOrdering         : function (callback) {
        this.setCallback(callback);
        this._openPhoneDialog(undefined, true);
        return this;
    },
    openCantLoginDialog : function (callback) {
        this.setCallback(callback);
        this._openPhoneDialog(undefined, undefined, "cant_login");
        return this;
    },
    openSendingDialog       : function (callback) {
        var that = this;
        that.setCallback(callback);
        this.getTemplate.call(this, 'sending', function(dialog_content) {
            that.openDialog.call(that, {});
        });
    },
    openRegistrationDialog  : function (callback, show_registration, registration_only, order_message) {
        var that = this,
            dialog_config = {};
        this.setCallback(callback);
        this.getTemplate.call(this, 'reg', function (dialog_content) {
            var $button = $('#join', dialog_content).unbind('click').bind('click', function (e) {
                    if ( that.validator.form() ) {
                        that.doRegister.call(that, $('form:first', dialog_content));
                    }
                    return false;
            }),
            $show_login_link = $('#show_login')
                .unbind('click')
                .bind('click', function (e) {
                    that.openLoginDialog.call(that);
                    return false;
            }),

            validation_config = $.extend(window.validation_config, that.default_validator_config.ui_functions);
            
            $("#registration", dialog_content).hide();
            if (! show_registration) {
                $("#dialog #ok").click(function() {
                    $("#dialog").dialog("close");
                    OrderHistoryHelper.loadHistory({});
                });
            } else {
                $("#dialog #ok").hide();
                $("#dialog").oneTime(2000, function() {
                    var height = (registration_only) ? "515px" : "700px";
                    $(".ui-dialog").animate(
                        { height: height },
                        { duration: 200,
                          easing:  "swing",
                          complete: function() {
                              $("#registration", dialog_content).fadeIn();
                        }
                    });
                });
            }
            if (registration_only) {
                dialog_config = { title: window.form_config.messages.thanks_for_registering };
                $("#registration", dialog_content).show();
                $("#registration_header", dialog_content).hide();
                $("#registration > h1", dialog_content).hide();
            }
            if (order_message) {
                $("#registration_header .progress-sub-title", dialog_content).html(order_message);
            }
            that.openDialog.call(that, validation_config, dialog_config);
        });
    },
    openCredentialsDialog  : function(callback){
        var that = this,
            dialog_config = {};
        this.setCallback(callback);
        this.getTemplate.call(this, 'credentials', function (dialog_content) {
            var $button = $('#save_credentials', dialog_content).unbind('click').bind('click', function (e) {
                if (that.validator.form()) {
                    that.doChangeCredentials.call(that, $('form:first', dialog_content));
                }
                return false;
            }),

            validation_config = $.extend(window.validation_config, that.default_validator_config.ui_functions);

            that.openDialog.call(that, validation_config, dialog_config);
        });
    },
    _setProgressBar         : function(val, timer, dialog_content, show_registration) {
        var that = this;
        timer.oneTime(700, function() {
            $(".ui-progressbar-value", dialog_content).animate({
                width: val + "%"
            }, 500 ,function() {
                if (val === 100) {
                    $(".ui-progressbar-value", dialog_content).addClass("success");
                    $("#dialog").dialog("option", "title", that.config.messages.order_sent);
                    $(".progress-sub-title", dialog_content).text(that.config.messages.ride_details);
                    $(".ui-dialog-title").addClass("success");

                    // animate dialog

                }
            });
        });
    },
    doJoin                  : function () {
        var that = this;
        that.openPhoneDialog(function() {
            that.openRegistrationDialog(function() {
                window.location.href = "/";
            }, true, true)
        });
    },
    doResetCredentials      : function(){
        var that = this;
        that.openCantLoginDialog(function(){
            that.openCredentialsDialog(function(){
                window.location.href = "/";
            });
        });
    },
    openDialog              : function (validation_config, dialog_config) {
        var config = $.extend(true, {}, this.config.dialog_config, dialog_config),
            $dialog = $('#dialog');
        if (validation_config) {
            this.initValidator($('form:first', $dialog), validation_config);
        }
        $dialog.dialog('option', config);
        if (! $dialog.dialog('isOpen') ) {
            $dialog.dialog('open');
        }
        $dialog.find("input:first").focus();

    },
    sendSMS                 : function (form) {
        var that = this,
            $button = $('#send_sms_verification').button('disable');
        if ( this.validator.element('#local_phone') ) {
            jQuery("input[name=local_phone]").next().removeClass("sms-button").addClass("input-helper").addClass("sending-code").children("div").text(that.config.messages.sending_code);
            
            $.ajax({
                url :that.config.urls.send_sms,
                type : 'post',
                data : $(form).serialize(),
                success : function (response) {
                    jQuery("input[name=local_phone]").next().removeClass("sending-code").addClass("code-sent").children("div").text(that.config.messages.code_sent);
                    jQuery("#verification_code").removeAttr('disabled').focus();
                },
                error :function (XMLHttpRequest, textStatus, errorThrown) {
                    alert('error send sms: ' + XMLHttpRequest.responseText);
                    $button.button('enable');
                }
            });
        }
    },
    setHelperButton         : function (context, id, callable) {
        if (context.currentElements.length && context.currentElements[0].id == id) {
            var $elem = $("div[htmlfor=" + id +"]").text("").parent();
            if ($elem.hasClass("sending-code")) { // skip if we are during sms sending
                return;
            }
            if (context.errorList.length == 0) {

                $elem.addClass("sms-button").unbind("mouseup").bind("mouseup", callable);
            } else {
                $elem.removeClass("sms-button").unbind("mouseup");
            }
        }
    },
    highlight: function(element, errorClass, validClass) {
        $(element).next().addClass(errorClass).removeClass(validClass).removeClass("red").removeClass("green");
        for (var key in this.config.error_messages) {
            if (this.config.error_messages[key] === this.validator.errorList[0].message) {
                $(element).next().addClass("red");
            }
        }
    },
    unhighlight: function(element, errorClass, validClass) {
        $(element).next().addClass(validClass).removeClass(errorClass).removeClass("red");
    },
    errorPlacement: function(error, element) {
        error.addClass('input-helper');
        $(element).after(error);
    },
    success: function (label) {
        label.text(this.config.messages.valid_field).parent().removeClass("red").addClass("green");
    }
});