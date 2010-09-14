var Registrator = Object.create({
    default_config           : {
        urls            : {
            login_form_template : '/',
            reg_form_template   : '/',
            phone_form_template : '/',
            check_username      : '/',
            login               : '/',
            send_sms            : '/',
            register            : '/'
        },
        dialog_config   : {
            autoOpen: false,
            resizable: false,
            modal: true,
            width: 500,
            zIndex:2000
        },
        messages        : {
            username_taken  : ''
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
    doRegister              : function (form, extra_form_data) {
        var that = this,
            extra_data = extra_form_data ? '&' + extra_form_data : '';
        if ( this.validator.form() ) {
            $.ajax({
                url :that.config.urls.register,
                type : 'post',
                data : $(form).serialize() + extra_data,
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
    _openPhoneDialog         : function (extra_form_data) {
        var that = this;
        this.getTemplate.call(this, 'phone', function (dialog_content) {
            var validation_config = {
                onkeyup: true,
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
            },
            $sms_button = $('form input#send_sms_verification', dialog_content).button()
               .unbind('click')
               .bind('click', function (e) {
                    that.sendSMS.call(that, this.form);
                    return false;
               }),
            $finish_button = $('form input#register', dialog_content).button()
               .unbind('click')
               .bind('click', function (e) {
                    that.doRegister.call(that, this.form, extra_form_data);
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
    openRegistrationDialog  : function (callback) {
        var that = this;
        this.setCallback(callback);
        this.getTemplate.call(this, 'reg', function (dialog_content) {
            var validation_config = {
                rules: {
                    username: {
                        required: true,
                        remote: that.config.urls.check_username
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
                        remote: that.config.messages.username_taken
                    }
                }
            },
            $button = $('form button', dialog_content).button()
                .unbind('click')
                .bind('click', function (e) {
                    if ( that.validator.form() ) {
                        that._openPhoneDialog.call(that, $('form:first', dialog_content).serialize());
                    }
                    return false;
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
                    alert('verification code: '+response);
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