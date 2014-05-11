# This Python file uses the following encoding: utf-8

import time
from django.core.urlresolvers import reverse

SELENIUM_USER_NAME = "selenium@waybetter.com"
SELENIUM_NEW_USER_NAME = "selenium_new@waybetter.com"
SELENIUM_SOCIAL_USERNAME = "selenium.waybetter.com"
SELENIUM_EMAIL = SELENIUM_USER_NAME
SELENIUM_STATION_USER_NAME = "selenium_station@waybetter.com"
SELENIUM_WS_USER_NAME = "selenium_ws@waybetter.com"
SELENIUM_USER_NAMES = [SELENIUM_USER_NAME, SELENIUM_NEW_USER_NAME, SELENIUM_STATION_USER_NAME, SELENIUM_WS_USER_NAME]
SELENIUM_PASSWORD = 'selenium'
SELENIUM_SOCIAL_PASSWORD = "***REMOVED***"
SELENIUM_PHONE = "0001234567"
SELENIUM_UNREGISTERED_PHONE = "9991234567"

SELENIUM_ADDRESS = u"רמת הגולן 1, אריאל"
SELENIUM_CITY_NAME = u'אריאל'

SELENIUM_PASSENGER = None
SELENIUM_STATION = None

SELENIUM_TEST_KEY = 'f60e09866cec247587776eaf2809a841919100a0'
SELENIUM_VERIFICATION_CODE = 3857
SELENIUM_WRONG_CODE = 0000

WAIT_TIMEOUT = 30 #sec

class SelemiumHelper():
    def login_as_selenium(self):
        sel = self.selenium
        sel.open(reverse('testing.setup_testing_env.create_selenium_test_data'))
        sel.open("/")
        self.wait_for_element_and_click_at("login_link")
        self.wait_for_element_and_type("username", SELENIUM_USER_NAME)
        sel.type("password", SELENIUM_PASSWORD)
        sel.click("login")
        self.wait_for_element_present("logout_link")

    def logout(self):
        #        self.wait_for_element_present("logout_link")
        self.assertTrue(self.selenium.is_element_present("logout_link"))
        self.selenium.click("logout_link")
        self.wait_for_element_present("login_link")
        self.selenium.open("/") # voodoo

    def login(self, wrong_username=False, wrong_password=False, username=None, password=None):
        """
        Do login. Assumes the login dialog is open when called.
        """

        if not username:
            username = SELENIUM_USER_NAME
        if not password:
            password = SELENIUM_PASSWORD
        if wrong_username:
            username= "wrong_email@waybetter.com"
        if wrong_password:
            password = "wrong_password"

        self.wait_for_element_and_type("username", username)
        self.selenium.type("password", password)
        self.selenium.click("login")
        time.sleep(1)

    def validate_phone(self, wrong_code=False, phone=SELENIUM_PHONE):
        """
        Do phone validation. Assumes the phone verification dialog is open when called.
        """
        sel = self.selenium
        # append the verification form with a hidden field that indicates that we are in test mode
        self.wait_for_element_visible("phone_verification_form")
        jquery = 'window.jQuery("#phone_verification_form").append("<input type=hidden name=test_key value=%s>")' % SELENIUM_TEST_KEY
        sel.get_eval(jquery)

        self.wait_for_element_and_type("local_phone", phone)
        self.wait_for_element_present("css=div.sms-button")
        time.sleep(1)
        sel.click_at("//form[@id='phone_verification_form']/fieldset/div","0 0")
        time.sleep(1)

        if wrong_code:
            self.wait_for_element_and_type("verification_code", SELENIUM_WRONG_CODE)
        else:
            self.wait_for_element_and_type("verification_code", SELENIUM_VERIFICATION_CODE)

        self.wait_for_element_and_click_at("//form[@id='phone_verification_form']/fieldset/div[2]")

    def register(self, email=SELENIUM_EMAIL, password=SELENIUM_PASSWORD, password_again=SELENIUM_PASSWORD, dont_click=False):
        """
        Do registration. Assumes the registration dialog is open when called.
        """
        self.wait_for_element_and_type("email", email)
        self.assert_element_and_type("password", password)
        self.assert_element_and_type("password_again", password_again)
        if not dont_click:
            self.selenium.click("join")

    def change_credentials(self, new_password, new_email=SELENIUM_EMAIL, dont_click=False):
        """
        Do change credentials. Assumes "/" is open.
        """
        self.wait_for_element_and_click_at("login_link")
        time.sleep(1) # allow the dialog to load, otherwise bad things happen
        self.wait_for_element_and_click_at("cant_login_link")
        self.wait_for_element_visible("phone_verification_form")
        self.validate_phone()
        self.wait_for_element_visible("registration_form")
        self.register(email=new_email, password=new_password, password_again=new_password, dont_click=True)
        if not dont_click:
            self.selenium.click("save_credentials")

    def social_login(self, provider_link_locator, provider_window_title, email_locator, password_locator, signin_locator):
        sel = self.selenium
        sel.click("login_link")
        self.wait_for_element_and_click_at(provider_link_locator)
        self.wait_for_window_and_select(provider_window_title)
        self.wait_for_element_and_type(email_locator, SELENIUM_SOCIAL_USERNAME)
        sel.type(password_locator, SELENIUM_SOCIAL_PASSWORD)
        sel.click(signin_locator)
        self.wait_for_window_closed(provider_window_title)
        self.wait_for_element_present("logout_link")
        self.logout()

    def social_authentication(self, provider_link_locator, provider_window_title, email_locator, password_locator, signin_locator):
        self.wait_for_element_and_click_at(provider_link_locator)
        self.wait_for_window_and_select(provider_window_title)
        self.wait_for_element_and_type(email_locator, SELENIUM_SOCIAL_USERNAME)
        self.selenium.type(password_locator, SELENIUM_SOCIAL_PASSWORD)
        self.selenium.click(signin_locator)
        self.wait_for_window_closed(provider_window_title)

    def book_order(self, address, dummy=False):
        if dummy:
            # append the verification form with a hidden field that indicates that we are in test mode
            jquery = 'window.jQuery("#order_form").append("<input type=hidden name=test_key value=%s>")' % SELENIUM_TEST_KEY
            self.selenium.get_eval(jquery)

        self.selenium.click("id_from_raw")
        self.selenium.type_keys("id_from_raw", address)
        self.wait_for_autocomplete_and_click(u"//html/body/ul/li/a[. = \"%s\"]" % address)
        self.selenium.click("order_button")
        self.wait_for_element_visible("ui-dialog-title-dialog")

    #
    # wait methods
    #
    def wait_for_condition(self, condition, timeout=WAIT_TIMEOUT, timeout_name=""):
        for i in range(timeout):
            try:
                if condition(): break
            except: pass
            time.sleep(1)
        else: self.fail("time out while waiting for: %s" % timeout_name)

    def wait_for_element_visible(self, locator, timeout=WAIT_TIMEOUT):
        self.wait_for_condition(lambda : self.selenium.is_visible(locator), timeout, "%s visible" % locator)

    def wait_for_element_present(self, locator, timeout=WAIT_TIMEOUT):
        self.wait_for_condition(lambda : self.selenium.is_element_present(locator), timeout, "%s present" % locator)

    def wait_for_element_and_click_at(self, element, x_y="0 0"):
        self.wait_for_element_present(element)
        self.selenium.mouse_down_at(element, x_y)
        time.sleep(2)
        if self.selenium.is_element_present(element):
            self.selenium.mouse_up_at(element, x_y)

        time.sleep(2)
        if self.selenium.is_element_present(element):
            self.selenium.click_at(element, x_y)

    def wait_for_element_and_type(self, element, text):
        self.wait_for_element_present(element)
        self.selenium.type(element, text)
        self.selenium.click(element)

    def wait_for_alert(self, alert=None, timeout=WAIT_TIMEOUT):
        if alert:
            self.wait_for_condition(lambda : alert == self.selenium.get_alert(), timeout, "alert %s" % alert)
        else:
            self.wait_for_condition(lambda : self.selenium.get_alert(), timeout, "alert")

    def wait_for_text(self, text, locator, timeout=WAIT_TIMEOUT):
        if not text:
            self.wait_for_condition(lambda : self.selenium.get_text(locator), timeout, "any text in %s" % locator )
        else:
            self.wait_for_condition(lambda : text == self.selenium.get_text(locator), timeout, "text %s" % text )

    def wait_for_text_present(self, text, timeout=WAIT_TIMEOUT):
        self.wait_for_condition(lambda : self.selenium.is_text_present(text), timeout, "text %s" % text)

    def wait_for_autocomplete_and_click(self, ac_element):
        self.wait_for_element_present(ac_element)
        self.selenium.mouse_over(ac_element)
        self.selenium.click(ac_element)

    def wait_for_window_and_select(self, title, timeout=WAIT_TIMEOUT):
        self.wait_for_condition(lambda : title in self.selenium.get_all_window_titles(), timeout, "window %s" % title)
        self.selenium.select_window("title=%s" % title)

    def wait_for_window_closed(self, title, timeout=WAIT_TIMEOUT):
        self.wait_for_condition(lambda : not title in self.selenium.get_all_window_titles(), timeout, "window closed %s" % title)
        # reselect the main window
        self.selenium.select_window("null")

    #
    # other methods
    #
    def assert_element_and_type(self, element, text):
        self.assertTrue(self.selenium.is_element_present(element))
        self.selenium.type(element, text)
        self.selenium.click(element)

    def type_and_click(self, element, text):
        self.selenium.type(element, text)
        self.selenium.click(element)

#    def add_jquery_locators(self):
#        self.selenium.add_location_strategy("jquery",
#            "var loc = locator; " +
#            "var attr = null; " +
#            "var isattr = false; " +
#            "var inx = locator.lastIndexOf('@'); " +
#            "if (inx != -1){ " +
#            "   loc = locator.substring(0, inx); " +
#            "   attr = locator.substring(inx + 1); " +
#            "   isattr = true; " +
#            "} " +
#            "var found = jQuery(inDocument).find(loc); " +
#            "if (found.length >= 1) { " +
#            "   if (isattr) { " +
#            "       return found[0].getAttribute(attr); " +
#            "   } else { " +
#            "       return found[0]; " +
#            "   } " +
#            "} else { " +
#            "   return null; " +
#            "}"
#        )

