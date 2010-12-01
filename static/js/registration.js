var Registrator = Object.create({
    default_config           : {
        urls            : {
            login_form_template         : '/',
            reg_form_template           : '/',
            phone_form_template         : '/',
            phone_code_form_template    : '/',
            sending_form_template       : '/',
            check_username              : '/',
            login                       : '/',
            send_sms                    : '/',
            update_profile              : '/',
            register                    : '/',
            validate_phone              : '/',
            check_phone                 : '/'
        },
        dialog_config   : {
            autoOpen: false,
            resizable: false,
            modal: true,
            width: 500,
            zIndex:2000
        },
        error_messages  : {
            username_taken          : '',
            invalid_email           : '',
            passwords_dont_match    : '',
            too_short               : '',
            too_long                : '',
            only_digits             : ''
        },
        messages        : {
            unique_username         : '',
            enter_email             : '',
            choose_password         : '',
            password_again          : '',
            checking_user           : '',
            valid_field             : '',
            enter_mobile            : '',
            phone_taken             : ''

        },
        callback        : function () {}
    },
    validator               : {},
    default_validator_config: {
        errorClass: 'ui-state-error',
        errorElement: 'span',
        onkeyup: false,
        focusCleanup: true
    },
    config                  : {},
    /**
     * Initializes this.config
     *
     * @param config
     * @return this
     */
    init                    : function (config) {
        // config will be the argument config
        // OR the global var 'form_config' provided in the template

        var _config = window.form_config ? form_config : {};
        config = config || _config;

        this.config = $.extend(true, {}, this.default_config, this.config, config);
        if (! $("#dialog").length) {
            $("<div id='dialog'></div>").hide().appendTo("body");
        }
        $("#dialog").dialog(this.config.dialog_config);
        return this;
    },
    initValidator           : function ($form, config) {
        var _config = $.extend(true, {}, this.default_validator_config, config);
        this.validator = $form.validate(_config);
        return this;
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
        var that = this;
        if ( this.validator.form() ) {
            $.ajax({
                url :that.config.urls.login,
                type : 'post',
                data : $(form).serialize(),
                success : function (response) {
                    $('#dialog').dialog('close');
                    if ( that.config.callback ) {
                        that.config.callback();
                    }
                },
                error: function(xhr) {
                    alert(xhr.responseText);
                }
            });
        }
    },
    _doDialogSubmit          : function (form, extra_form_data, url) {
        var that = this,
            data = extra_form_data ? extra_form_data + '&' + $(form).serialize() : $(form).serialize();
        if ( this.validator.form() ) {
            $.ajax({
                url :url,
                type : 'post',
                data : data,
                success : function (response) {
                    $('#dialog').dialog('close');
                    if ( that.config.callback ) {
                        that.config.callback();
                    }
                },
                error :function (XMLHttpRequest, textStatus, errorThrown) {
                    alert('error: ' + XMLHttpRequest.responseText);
                }
            });
        }
    },
    doProfileUpdate         : function(form, extra_form_data) {
        this._doDialogSubmit(form, extra_form_data, this.config.urls.update_profile);
    },
    doPhoneValidation       : function(form) {
        this._doDialogSubmit(form, null, this.config.urls.validate_phone);
    },
    doRegister              : function (form, extra_form_data) {
        this._doDialogSubmit(form, extra_form_data, this.config.urls.register);
    },
    openLoginDialog         : function (callback) {
        var that = this;
        this.setCallback(callback);
        this.getTemplate.call(this, 'login', function (dialog_content) {
            var validation_config = {
                rules: {
                    username: "required",
                    password: "required"
                }
            },
            $button = $('form button', dialog_content).button()
                .unbind('click')
                .bind('click', function (e) {
                    that.doLogin.call(that, this.form);
                    return false;
               }),
            $show_register_link = $('#show_register')
                .unbind('click')
                .bind('click', function (e) {
                    that.openRegistrationDialog.call(that);
                    return false;
            });
            that.openDialog.call(that, validation_config);
        });
    },
    openCodeDialog           : function (callback) {
        var that = this;
        that.setCallback(callback);
        this.getTemplate.call(this, 'phone_code', function(dialog_content) {
            var extra_form_data = $('#profile_form').serialize(),
            validation_config = {
                rules: {
                    verification_code: "required"
                }
            },
            $finish_button = $('form input#register', dialog_content).button();
            $('form', dialog_content).submit(function(e) {
                console.log(this);
                e.preventDefault();
                that.doProfileUpdate($('form', dialog_content), extra_form_data);
            });
            that.openDialog.call(that, validation_config);
        });
    },
    _openPhoneDialog         : function (extra_form_data) {
        var that = this;
        this.getTemplate.call(this, 'phone', function (dialog_content) {
            var validation_config = {
                errorClass: "inputError",
                validClass: "inputValid",
                focusInvalid: false,
                focusCleanup: true,
                wrapper: "div",
                highlight: function(element, errorClass, validClass) {
                    console.log("highlight: " + this);
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
                    if (! $(element).next().hasClass('input-helper')) {
                        $(error).addClass('input-helper');
                        $(element).after(error);
                    }
                },
                success: function (label) {
                    console.log("success: " + this);
                    label.text(that.config.messages.valid_field).parent().removeClass("red").addClass("green");
                    that.validator.element($("#local_phone"));
                },
                rules: {
                    verification_code: {
                        required    : true,
                        digits      : true,
                        minlength   : 4,
                        maxlength   : 4
                    },
                    local_phone: {
                        required    : true,
                        remote      : that.config.urls.check_phone,
                        digits      : true,
                        minlength   : 10,
                        maxlength   : 11
                    }
                },
                messages: {
                    local_phone: {
                        required    : that.config.messages.enter_mobile,
                        digits      : that.config.error_messages.only_digits,
                        minlength   : that.config.error_messages.too_short,
                        maxlength   : that.config.error_messages.too_long,
                        remote      : that.config.messages.phone_taken
                    }
                }
            },
            $sms_button = $('form input#send_sms_verification', dialog_content).button()
               .unbind('click')
               .bind('click', function (e) {
                    that.sendSMS.call(that, this.form);
                    return false;
               }),
            $finish_button = $('form input#validate', dialog_content).button()
               .unbind('click')
               .bind('click', function (e) {
                    that.doPhoneValidation.call(that, this.form, extra_form_data);
                    return false;
               }),
            $phone_input = $('form input#local_phone', dialog_content)
                .unbind('keyup')
                .bind('keyup', function(e) {
                    if (that.validator.element($phone_input)) {
                        $sms_button.button("enable");
                    } else {
                        $sms_button.button("disable");
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

            });
            that.openDialog.call(that, validation_config);
        });
    },
    openPhoneDialog         : function (callback) {
        this.setCallback(callback);
        this._openPhoneDialog();
        return this;
    },
    openSendingDialog       : function (callback) {
        var that = this;
        that.setCallback(callback);
        this.getTemplate.call(this, 'sending', function(dialog_content) {
            that.openDialog.call(that, {});
        });
    },
    openRegistrationDialog  : function (callback, progress_only) {
        var that = this;
        this.setCallback(callback);
        this.getTemplate.call(this, 'reg', function (dialog_content) {
            var validation_config = {
                errorClass: "inputError",
                validClass: "inputValid",
                focusInvalid: false,
                focusCleanup: false,
                wrapper: "div",
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
                    error.addClass('input-helper');
                    $(element).after(error);
                },
                success: function (label) {
                    label.text(that.config.messages.valid_field).parent().removeClass("red").addClass("green");
                },
                rules: {
                    username: {
                        required: true,
                        remote: {
                            url: that.config.urls.check_username,
                            beforeSend: function() {
                                $("#registration_form").find("[htmlfor=username]").text(that.config.messages.checking_user).parent().removeClass("red").removeClass("green");
                            }
                        }
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
                        required    : that.config.messages.unique_username,
                        remote      : that.config.error_messages.username_taken
                    },
                    email: {
                        required    : that.config.messages.enter_email,
                        email       : that.config.error_messages.invalid_email
                    },
                    password: {
                        required    : that.config.messages.choose_password
                    },
                    password_again: {
                        required    : that.config.messages.password_again,
                        equalTo     : that.config.error_messages.passwords_dont_match    
                    }
                }
            },
            $button = $('#join', dialog_content).unbind('click').bind('click', function (e) {
                    if ( that.validator.form() ) {
                        that._openPhoneDialog.call(that, $('form:first', dialog_content).serialize());
                    }
                    return false;
               }),
            $not_now_button = $('#not_now').unbind('click').bind('click', function (e) {
                $("#dialog").dialog('close');
            }),
            $show_login_link = $('#show_login')
                .unbind('click')
                .bind('click', function (e) {
                    that.openLoginDialog.call(that);
                    return false;
            });
            that.openDialog.call(that, validation_config);
        });
    },
    openDialog              : function (validation_config) {
        var config = $.extend(true, {}, this.config.dialog_config),
            $dialog = $('#dialog');
        this.initValidator($('form:first', $dialog), validation_config);
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
            $.ajax({
                url :that.config.urls.send_sms,
                type : 'post',
                data : $(form).serialize(),
                success : function (response) {
                    $('#verification_code').removeAttr('disabled').focus();
                },
                error :function (XMLHttpRequest, textStatus, errorThrown) {
                    alert('error: ' + XMLHttpRequest.responseText);
                    $button.button('enable');
                }
            });
        }
    }
});