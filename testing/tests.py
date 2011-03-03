# -*- coding: utf-8 -*-

# don't forget to run a selenium server while running integration tests, see: http://seleniumhq.org/docs/05_selenium_rc.html#installation
# to use jquery locators you must modify RemoteRunner.html , see http://stackoverflow.com/questions/2814007/how-to-i-add-a-jquery-locators-to-selenium-remote-control

import setup_testing_env
from django.test import TestCase
from django.core.urlresolvers import reverse
from selenium import selenium
from selenium_helper import SelemiumHelper, SELENIUM_PHONE, SELENIUM_TEST_KEY, SELENIUM_VERIFICATION_CODE, SELENIUM_USER_NAME, SELENIUM_PASSWORD, SELENIUM_SOCIAL_USERNAME, SELENIUM_SOCIAL_PASSWORD
import time

APPLICATION_UNDER_TEST = "http://localhost:8000"
#APPLICATION_UNDER_TEST = "http://3.latest.waybetter-app.appspot.com/"
#APPLICATION_UNDER_TEST = "http://www.waybetter.com/"

class SeleniumTests(TestCase, SelemiumHelper):
    fixtures = ['countries.yaml']
    selenium = None

    def setUp(self):
        self.verificationErrors = []
        self.selenium = selenium("localhost", 4444, "*firefox", APPLICATION_UNDER_TEST)
        self.selenium.start()
        self.selenium.window_maximize()

    def test_login(self):
        sel = self.selenium
        self.login_as_selenium()
        self.logout()

        # login from join dialog
        sel.click("join_link")
        sel.click("login_link")
        self.wait_for_element_and_type("username", SELENIUM_USER_NAME)
        self.wait_for_element_and_type("password", SELENIUM_PASSWORD)
        sel.click("login")

        self.wait_for_element_present("logout_link")
        self.logout()

        # social login (Google)
        self.do_social_login("css=.google", "Google Accounts", "Email", "Passwd", "signIn")

        # Facebook and Twitter only allow waybetter.com requests
        if APPLICATION_UNDER_TEST == 'http://www.waybetter.com':
            self.do_social_login("css=.facebook", "Login | Facebook", "email", "pass", "login")
            self.do_social_login("css=.twitter", "Twitter", "username_or_email", "password", "Allow")

    def test_passenger_home(self):
        sel = self.selenium
        self.login_as_selenium()

        self.assertTrue(sel.is_element_present("history_tab_btn"))
        self.assertTrue(sel.is_element_present("profile_tab_btn"))
        self.assertTrue(sel.is_element_present("stations_tab_btn"))
        self.assertTrue(sel.is_element_present("mobile_tab_btn"))
        self.assertTrue(sel.is_element_present("id_from_raw"))
        self.assertTrue(sel.is_element_present("id_to_raw"))
        self.assertTrue(sel.is_element_present("order_button"))
        self.assertTrue(sel.is_element_present("feedback_peal"))

    def test_change_password(self):
        sel = self.selenium
        self.login_as_selenium()

        # change password and logout
        self.wait_for_element_present("profile_tab_btn")
        sel.click("profile_tab_btn")
        self.wait_for_element_present("id_password")
        sel.type("id_password", "newpassword")
        sel.type("id_password2", "newpassword")
        sel.click(u"//input[@value='שמירה']")
        self.wait_for_alert("Changes saved!", timeout=10)
        self.logout()

        # log in using old password (fail)
        sel.click("login_link")
        self.wait_for_element_present("login")
        sel.type("username", SELENIUM_USER_NAME)
        sel.type("password", SELENIUM_PASSWORD)
        sel.click("login")
        self.wait_for_element_present("login_error")

        # log in using new password (succeed)
        sel.type("password", "newpassword")
        sel.click("login")
        self.wait_for_element_present("logout_link")

    def test_history_page(self):
        sel = self.selenium
        self.login_as_selenium()

        sel.click("history_tab_btn")
        self.wait_for_element_present("orders_history_grid")
        self.assertTrue(sel.is_element_present("search_button"))
        self.assertTrue(sel.is_element_present("reset_button"))

        # test sorting
        self.wait_for_text(u"היכל נוקיה", "//div[@id='orders_history_grid']/table/tbody/tr[2]/td[2]")
        # bug? - double click is needed
        sel.click("history_header_label_1")
        sel.click("history_header_label_1")
        self.wait_for_text(u"גאולה 1 תל אביב", "//div[@id='orders_history_grid']/table/tbody/tr[2]/td[2]")

    def test_phone_verification_form(self):
        sel = self.selenium
        sel.open("/")
        sel.click("join_link")
        self.wait_for_element_present("local_phone")

        # append the verification form with a hidden field that indicates that we are in test mode
        jquery = 'window.jQuery("#phone_verification_form").append("<input type=hidden name=test_key value=%s>")' % SELENIUM_TEST_KEY
        sel.get_eval(jquery)

        sel.type_keys("local_phone", SELENIUM_PHONE)
        sel.click("local_phone")
        self.wait_for_element_present("css=div.sms-button")
        time.sleep(1)
        sel.click_at("//form[@id='phone_verification_form']/fieldset/div","0 0")
        time.sleep(1)

        # wrong code
        sel.type("verification_code", "1234")
        sel.click("verification_code")
        self.wait_for_element_and_click_at("//form[@id='phone_verification_form']/fieldset/div[2]")
        self.wait_for_element_present("css=.inputError")

        # correct code
        sel.type("verification_code", SELENIUM_VERIFICATION_CODE)
        sel.click("verification_code")
        self.wait_for_element_and_click_at("//form[@id='phone_verification_form']/fieldset/div[2]")

        self.wait_for_element_present("email")


    def test_join_internal(self):
        sel = self.selenium
        self.validate_phone_and_get_registration_form()

        sel.type("email", SELENIUM_USER_NAME)
        sel.type("password", SELENIUM_PASSWORD)
        sel.type("password_again", SELENIUM_PASSWORD)
        sel.click("join")
        self.wait_for_element_present("logout_link")
        self.logout()

    def test_autocomplete(self):
        sel=self.selenium
        sel.open("/")

        sel.type_keys("id_from_raw", u"אל")
        self.wait_for_autocomplete_and_click(u"//html/body/ul/li/a[. = \"אלנבי 1, תל אביב יפו\"]")

        sel.type_keys("id_to_raw", u"הרצ")
        self.wait_for_autocomplete_and_click(u"//html/body/ul/li/a[. = \"הרצל 1, תל אביב יפו\"]")

        self.wait_for_text_present(u"מחיר נסיעה משוער")

    def test_login_from_join_page(self):
        pass

    def tearDown(self):
        self.client.get(reverse('testing.setup_testing_env.destroy_selenium_test_data'))
        self.selenium.stop()
        self.assertEqual([], self.verificationErrors)
