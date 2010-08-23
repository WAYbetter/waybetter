var onRegisterSuccess;

var loginState = {
    init            : function (self) {},
    doLogin         : function (self) {},
    registerMode    : function (self) {},
    dialogSettings  : {},
    buildDialog     : function (container) {}
};

var registerState = {
    init                : function (self) {},
    doContinue          : function (self) {},
    doSubmit            : function (self) {},
    phoneVerification   : function (self) {},
    sendSMSVerification : function (self) {},
    loginMode           : function (self) {},
    dialogSettings      : function (self) {},
    buildDialog         : function (container) {}
};

function openSignupDialog(callback, showPhoneVerificationOnly) {};

$(document).ready(function() {
    var container = $("<div></div>").attr('id', "dialog-form").appendTo("body").hide();
    loginState.buildDialog(container);
    openid.init('openid_identifier');
});

/*************************************************************
/*************************************************************
/*************************************************************/

Object.create = Object.create || function (p) {
    if ( arguments.length != 1 ) {
        throw new Error("Can't simulate 2nd arg");
    }
    function f() {};
    f.prototype = p;
    return new f();
};

var Registrator = Object.create({
    default_config                  : {
        urls    : {
            login_form_template : '/',
            reg_form_template   : '/',
            phone_form_template : '/',
            check_username      : '/'
        },
        dialog_defaults         : {
            modal: true,
            width: 350,
            height: 200
        },
        messages                : {
            username_taken  : ''
        }
    },
    init                    : function (config) {
        // config will be the argument config
        // OR the global var 'form_config' provided in the template
        config = config || form_config || {};
        this.config = $.extend(true, {}, this.default_config, config);
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
    getTemplate              : function (template_name, callback) {
        var that = this;
        $.ajax({
            url : this.config.urls[template_name+'_form_template'],
            type : 'get',
            success : function (template) {
                // inject the form into the DOM
                var dialog = $('#dialog').empty().append(template);
                that.init.call(that);
                return callback(dialog);
            }
        });
    },
    doLogin                 : function () {},
    doRegister              : function () {},
    openLoginDialog         : function (dialog_config) {
        var that = this;
        this.getTemplate.call(this, 'login', function (dialog_content) {
            var validation_config = {
                errorClass: 'my-ui-state-error',
                rules: {
                    username: "required",
                    password: "required"
                }
            },
            $button = $('form > button', dialog_content).button()
                .unbind('click')
                .bind('click', function (e) {
                    that.doLogin.call(that, this.form, validation_config);
                    return false;
               }),
            $show_register_link = $('#show_register')
                .unbind('click')
                .bind('click', function (e) {
                    that.openRegistrationDialog.call(that, dialog_config);
                    return false;
            });
            that.openDialog.call(that, dialog_config);
        });
    },
    openPhoneDialog         : function (dialog_config) {
        var that = this;
        this.getTemplate.call(this, 'phone', function (dialog_content) {
            var validation_config = {
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
            },
            $sms_button = $('form > button#send_sms_verification', dialog_content).button()
               .unbind('click')
               .bind('click', function (e) {
                    that.sendSMS.call(that, this.form, validation_config);
                    return false;
               }),
            $finish_button = $('form > button#send_sms_verification', dialog_content).button()
               .unbind('click')
               .bind('click', function (e) {
                    that.doRegister.call(that, this.form, validation_config);
                    return false;
               });
            that.openDialog.call(that, dialog_config);
        });
    },
    openRegistrationDialog  : function (dialog_config) {
        var that = this;
        this.getTemplate.call(this, 'reg', function (dialog_content) {
            var validation_config = {
                errorClass: 'my-ui-state-error',
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
            };
            that.openDialog.call(that, dialog_config);
        });
    },
    openDialog              : function (dialog_config) {
        var config = $.extend(true, {}, this.config.dialog_defaults, dialog_config),
            $dialog = $('#dialog');
        if ( $dialog.dialog('isOpen') ) {
            $dialog.dialog('option', config);
        } else {
            $dialog.dialog(config);
        }
    },
    sendSMS                 : function () {

    }
});


/*************************************************************
/*************************************************************
/*************************************************************/

/**
 *  Class FormController
 *
 * Note on Validation :
 *
 * Each field that should be validated will be
 * added a class with the value of the name of
 * the requested validation function.break
 * e.g.:
 * this input:
 * <input type="text" class="is_value" />
 * will be checked that it is not empty.
 */
FormController = function() {
	this.f_html		= null;
	this.f_jq		= null;
	this.options	= {};
	this.elements	= {};
};
FormController.prototype = {
	/**
	 * gets an object that maps form name to a config object
	 * iterates over the object and adds the submit event
	 * listener to every form
	 * @param  Object   configs : a map of { name : config }
	 */
	bind				: function (configs) {
		var this_ = this;
		$.each(configs, function(name, config){
			if(document.forms[name]) {
                $(':button[type=submit],:input[type=submit]', document.forms[name]).bind('click', function(e){
                    if($(e.target).attr('name').length && $(e.target).attr('name') == 'action') {
                        $.extend(config, { action : $(e.target).val() });
                    };
                    return this_.submit.call(this_, this.form, config);
                });
            }
		});
	},
	init				: function (form, options) {
		var this_ = this;
        this.f_html		= form || {};
		this.f_jq		= $(form) || {};
		this.options	= $.extend(true, {
	        validation	    : {},
			url			    : this.f_jq.attr('action') || '/',
	        type		    : this.f_jq.attr('method') || 'POST',
	        dont_post	    : false,
	        data_type	    : 'text',
            reset_after_send: true,
            callback        : null,
	        editor		    : {}
	    }, options || {});
		this.elements = {};
		if(this.f_html.elements) {
			$.each(this.f_html.elements, function (i, el) {
				if($(el).attr('name')) {
					this_.elements[$(el).attr('name')] = el;
				}
			});
		}
	},
	validate			: function () {
		var valid = true;
		this.extractValidation();
		if(this.options.validation && typeof this.options.validation != 'undefined') {
			var this_ = this;
			$.each(this.options.validation, function(field, method){
				var _checked = false;
                // first check that there's a field with this name and that it's not disabled
				if(this_.elements[field] != null && !this_.elements[field].disabled) {
					try {
						if(this_[method] && $.isFunction(this_[method])) {
							if(!this_[method].call(this_, field)) {
								this_.alert_field.call(this_, field);
								valid = false;
							} else {
								this_.clear_alert.call(this_, field);
							}
						}
					} catch(e){alert(e);}
				} else if(this_.elements[field+'[]'] != null && !this_.elements[field+'[]'].disabled) {
					try {
						/*
						 * in case there's a specification for a validation of checkboxes
						 * run an 'OR' test to verify that at least one is checked
						 */
						$.each(this_.elements[field+'[]'], function(index, box){
							_checked = _checked || box.checked;
						});
						valid = _checked;
					} catch(e){alert(e);}
				}
			});
		} else {
			valid = false;
			throw new Error("Form's validation map is missing.");
		}
		return valid;
	},
	/**
	 * the function that is called on the onsubmit event fire
	 * of the form object
	 * @return Boolean false : !! must return false to prevent from redirect to the action url
	 */
	submit				: function (form, options) {
		this.init(form, options);
        if(this.validate()) {
			if(this.before()) {
				if(this.options.dont_post) {
					this.after(this.f_jq.serialize());
				} else {
					this.send();
				}
			}
		}
		return false;
	},
	/**
	 * handles the ajax request
	 * @return Object response : the server's response
	 */
	send				: function () {
		var this_ = this;
		$.ajax({
			type	: this_.options.type,
			url		: this_.options.url,
			data	: this_.f_jq.serialize(),
			dataType: this_.options.data_type,
			success	: function(response){
                this_.after.call(this_, response);
			}
		});
	},
	/**
	 * a handler for pre ajax request logic
	 * @return Boolean continue : whether to continue to send
	 */
	before				: function () {
		// enable catching form's multiple submit and passing it to send
		if(this.options.action != null && this.options.action != '') {
			this.options.url = this.options.url + this.options.action;
		}
		return true;
	},
	/**
	 * a handler for ajax response logic and calling callbacks
	 * @return Object
	 */
	after				: function (response) {
        var o = this.options;
        if(o.reset_after_send) {
            this.f_html.reset();
        }
        if(o.callback && typeof o.callback == 'function') {
			o.callback(response);
		} else {
            alert(response);
		}
	},
	extractValidation	: function () {
		var additional_validation = {};
		$.each(this.elements, function (el_name, el) {
			// disabled fields are not counted
			if(!el.disabled) {
				var classes = $(el).attr('class').split(' ');
				$.each(classes, function (i, _class) {
					// allowing one check per field
					if(_class && _class.indexOf('is_') === 0) {
						additional_validation[el_name] = _class;
					}
				});
			}
		});
		$.extend(this.options.validation, additional_validation);
	},
	alert_field			: function (el_name) {
		$(this.elements[el_name]).addClass('field_alert');
	},
	clear_alert			: function (el_name) {
		$(this.elements[el_name]).removeClass('field_alert');
	},
	/*
	 * validation functions :
	 */
	is_value			: function (el_name) {
		var val = $(this.elements[el_name]).val();
		return val && $.trim(val) != '' && typeof val != 'undefined';
	},
	is_alpha			: function (el_name) {
		return this._validate($(this.elements[el_name]), /[^a-zA-Z\s_-]/g);
	},
	is_numeric			: function (el_name) {
		return this._validate($(this.elements[el_name]), /[\D]/g);
	},
	is_alphanumeric		: function (el_name) {
		return this._validate($(this.elements[el_name]), /[^\w\s-]/g);
	},
	_validate			: function (el, pat ){
		return this.is_value(el.attr('name')) ? !pat.test(el.val()) : false;
	}
};
