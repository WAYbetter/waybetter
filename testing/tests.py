# -*- coding: utf-8 -*-

# don't forget to run a selenium server while running integration tests, see: http://seleniumhq.org/docs/05_selenium_rc.html#installation
# to use jquery locators you must modify RemoteRunner.html , see http://stackoverflow.com/questions/2814007/how-to-i-add-a-jquery-locators-to-selenium-remote-control

#import setup_testing_env
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
        sel.open("/")
        self.wait_for_element_and_click_at("login_link")

        self.do_login(wrong_username=True)
        self.assertTrue(sel.get_text("login_error"))

        self.do_login(wrong_password=True)
        self.assertTrue(sel.get_text("login_error"))

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

    def test_social_login(self):
        sel = self.selenium
        sel.open("/")

        # Google social login
        self.do_social_login("css=.google", "Google Accounts", "Email", "Passwd", "signIn")

        # Facebook and Twitter only allow waybetter.com requests
        if APPLICATION_UNDER_TEST == 'http://www.waybetter.com':
            self.do_social_login("css=.facebook", "Login | Facebook", "email", "pass", "login")
            self.do_social_login("css=.twitter", "Twitter", "username_or_email", "password", "Allow")

    def test_passenger_home(self):
        sel = self.selenium
        self.login_as_selenium()

        required_elements = ["history_tab_btn", "profile_tab_btn", "stations_tab_btn", "mobile_tab_btn", "id_from_raw",
                             "id_to_raw", "order_button", "feedback_peal"]

        for element in required_elements:
            self.assertTrue(sel.is_element_present(element))
        
    def test_change_password(self):
        sel = self.selenium
        self.login_as_selenium()

        # change password and logout
        self.wait_for_element_and_click_at("profile_tab_btn")
        self.wait_for_element_and_type("id_password", "newpassword")
        sel.type("id_password2", "newpassword")
        sel.click("save_profile_changes")
        self.wait_for_alert("Changes saved!")
        self.logout()

        # log in using old password (fail)
        sel.click("login_link")
        self.wait_for_element_and_type("username", SELENIUM_USER_NAME)
        sel.type("password", SELENIUM_PASSWORD)
        sel.click("login")
        self.wait_for_element_present("login_error")

        # log in using new password (succeed)
        sel.type("password", "newpassword")
        sel.click("login")
        self.wait_for_element_present("logout_link")

#    def test_change_phone(self):
#        sel = self.selenium
#        self.login_as_selenium()
#        self.wait_for_element_and_click_at("profile_tab_btn")
#        self.wait_for_element_and_type("local_phone", SELENIUM_PHONE.replace("000","111"))
#        sel.click("save_profile_changes")
#

    def test_history_page(self):
        sel = self.selenium
        self.login_as_selenium()

        self.wait_for_element_and_click_at("history_tab_btn")
        self.wait_for_element_present("orders_history_grid")
        self.assertTrue(sel.is_element_present("search_button"))
        self.assertTrue(sel.is_element_present("reset_button"))

        # choose address from history
        sel.click("id_from_raw")
        sel.click("css=.input_history_helper")
        sel.click("//div[@id='orders_history_grid']/table/tbody/tr[2]/td[2]")
        time.sleep(1)
        self.assertTrue(sel.get_value("id_from_raw") == sel.get_text("//div[@id='orders_history_grid']/table/tbody/tr[2]/td[2]"))

        # sort history
        self.wait_for_text(u"היכל נוקיה", "//div[@id='orders_history_grid']/table/tbody/tr[2]/td[2]")
        # bug? - double click is needed
        sel.click("history_header_label_1")
        sel.click("history_header_label_1")
        self.wait_for_text(u"גאולה 1 תל אביב", "//div[@id='orders_history_grid']/table/tbody/tr[2]/td[2]")

    def test_phone_verification(self):
        sel = self.selenium
        sel.open("/")
        sel.click("join_link")
        self.wait_for_element_present("local_phone")

        # wrong code, make sure we get an error
        self.do_validate_phone(wrong_code=True)
        self.wait_for_element_present("css=.inputError")

        # correct code, we should get the registration dialog
        self.do_validate_phone()
        self.assertTrue(sel.is_visible("ui-dialog-title-dialog"))

    def test_join(self):
        sel = self.selenium
        sel.open("/")

        sel.click("join_link")
        self.wait_for_element_present("local_phone")
        self.do_validate_phone()

        # illegal email
        self.wait_for_element_and_type("email", "not_a_valid_email")
        self.wait_for_text_present(u'כתובת דוא"ל לא חוקית')
        self.wait_for_element_and_type("email", SELENIUM_USER_NAME)
        sel.click("join")
        self.assertTrue(sel.is_visible("ui-dialog-title-dialog")) # still in registration dialog

        # non matching passwords
        self.assert_element_and_type("password", SELENIUM_PASSWORD)
        self.assert_element_and_type("password_again", "not_the_same_password")
        self.wait_for_text_present(u'אין התאמה בין הסיסמאות')
        sel.click("join")
        self.assertTrue(sel.is_visible("ui-dialog-title-dialog")) # still in registration dialog

        # legal registration
        self.assert_element_and_type("password_again", SELENIUM_PASSWORD)
        sel.click("join")
        self.wait_for_element_present("logout_link")
        self.logout()

    def test_autocomplete(self):
        sel = self.selenium
        sel.open("/")

        sel.type_keys("id_from_raw", u"אל")
        self.wait_for_autocomplete_and_click(u"//html/body/ul/li/a[. = \"אלנבי 1, תל אביב יפו\"]")

        sel.type_keys("id_to_raw", u"הרצ")
        self.wait_for_autocomplete_and_click(u"//html/body/ul/li/a[. = \"הרצל 1, תל אביב יפו\"]")

        self.wait_for_text_present(u"מחיר נסיעה משוער")

    def test_order_as_passenger(self):
        sel = self.selenium
        self.login_as_selenium()

        sel.type_keys("id_from_raw", u"רמת הגולן 1, אריאל")
        self.wait_for_autocomplete_and_click(u"//html/body/ul/li/a[. = \"רמת הגולן 1, אריאל\"]")


    def tearDown(self):
        self.selenium.open(reverse('testing.setup_testing_env.destroy_selenium_test_data'))
        self.selenium.stop()
        self.assertEqual([], self.verificationErrors)
