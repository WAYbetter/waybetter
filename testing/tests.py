# -*- coding: utf-8 -*-

# don't forget to run a selenium server while running integration tests, see: http://seleniumhq.org/docs/05_selenium_rc.html#installation
# to use jquery locators you must modify RemoteRunner.html , see http://stackoverflow.com/questions/2814007/how-to-i-add-a-jquery-locators-to-selenium-remote-control

#import setup_testing_env
from django.test import TestCase
from django.core.urlresolvers import reverse
from selenium import selenium
from selenium_helper import SelemiumHelper, SELENIUM_PASSWORD, SELENIUM_EMAIL, SELENIUM_ADDRESS, SELENIUM_PHONE, SELENIUM_STATION_USER_NAME
import time
import logging

APPLICATION_UNDER_TEST = "http://localhost:8000/"
#APPLICATION_UNDER_TEST = "http://3.latest.waybetter-app.appspot.com/"
#APPLICATION_UNDER_TEST = "http://www.waybetter.com/"

class SeleniumTests(TestCase, SelemiumHelper):
    fixtures = ['countries.yaml']
    selenium = None

    def setUp(self):
        self.verificationErrors = []
        self.selenium = selenium("localhost", 4444, "*firefox", APPLICATION_UNDER_TEST)
#        self.selenium.set_timeout(30000) # milisecond
#        self.selenium.set_speed(50) # milisecond
        self.selenium.start()
        self.selenium.window_maximize()

    def test_login(self):
        logging.info("testing login")
        sel = self.selenium
        sel.open("/")
        self.wait_for_element_and_click_at("login_link")

        self.login(wrong_username=True)
        self.assertTrue(sel.get_text("login_error"))

        self.login(wrong_password=True)
        self.assertTrue(sel.get_text("login_error"))

        self.login_as_selenium()
        self.logout()

        # login from join dialog
        sel.click("join_link")
        self.wait_for_element_and_click_at("login_link")
        self.login()

        self.wait_for_element_present("logout_link")
        self.logout()

    def test_social_login(self):
        logging.info("testing social login")
        sel = self.selenium
        sel.open("/")

        # Google social login
        self.social_login("css=.google", "Google Accounts", "Email", "Passwd", "signIn")

        # Facebook and Twitter only allow waybetter.com requests
        if APPLICATION_UNDER_TEST == 'http://www.waybetter.com/':
            self.social_login("css=.facebook", "Login | Facebook", "email", "pass", "login")
            self.social_login("css=.twitter", "Twitter", "username_or_email", "password", "allow")

    def test_passenger_home(self):
        logging.info("testing passenger home")
        sel = self.selenium
        self.login_as_selenium()

        required_elements = ["history_tab_btn", "profile_tab_btn", "stations_tab_btn", "mobile_tab_btn", "id_from_raw",
                             "id_to_raw", "order_button", "feedback_peal"]

        for element in required_elements:
            self.assertTrue(sel.is_element_present(element))

    def test_change_password(self):
        logging.info("testing change password")
        sel = self.selenium
        self.login_as_selenium()

        # change password and logout
        self.wait_for_element_and_click_at("profile_tab_btn")
        self.wait_for_element_and_type("id_password", "newpassword")
        self.type_and_click("id_password2", "newpassword")
        sel.click("save_profile_changes")
        self.wait_for_alert("Changes saved!")
        self.logout()

        # log in using old password (fail)
        sel.click("login_link")
        self.login()
        self.assertTrue(sel.get_text("login_error"))

        # log in using new password (succeed)
        self.type_and_click("password", "newpassword")
        sel.click("login")
        self.wait_for_element_present("logout_link")

    def test_change_phone(self):
        logging.info("testing change phone")
        sel = self.selenium
        new_phone = "0001234567"

        self.login_as_selenium()
        self.wait_for_element_and_click_at("profile_tab_btn")
        self.wait_for_element_present("change_phone")

#        can't get this click to work, fails the test
        sel.click("change_phone")
        sel.mouse_down("change_phone")
        sel.mouse_up("change_phone")
        self.validate_phone(phone=new_phone)
        self.wait_for_text(new_phone, "current_phone")

    def test_history_page(self):
        logging.info("testing history page")
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
        logging.info("testing phone verification")
        sel = self.selenium
        sel.open("/")
        sel.click("join_link")
        self.wait_for_element_present("local_phone")

        # wrong code, make sure we get an error
        self.validate_phone(wrong_code=True)
        self.wait_for_element_present("css=.inputError")

        # correct code, we should get the registration dialog
        self.validate_phone()
        self.wait_for_element_present("join")
        self.register()
        self.wait_for_element_present("logout_link")
        self.logout()

        # try use the same phone again
        sel.click("join_link")
        self.wait_for_element_and_type("local_phone", SELENIUM_PHONE)
        self.wait_for_text_present(u"הטלפון כבר רשום")


    def test_registration(self):
        logging.info("testing registration")
        sel = self.selenium
        sel.open("/")

        self.wait_for_element_and_click_at("join_link")
        self.wait_for_element_present("local_phone")
        self.validate_phone()

        # illegal registration
        self.register("not_a_valid_email", SELENIUM_PASSWORD, "non_matching_password", dont_click=True)
        self.wait_for_text_present(u'כתובת דוא"ל לא חוקית')
        self.wait_for_text_present(u'אין התאמה בין הסיסמאות')

        # still in registration dialog
        self.assertTrue(sel.is_visible("ui-dialog-title-dialog"))

        # legal registration
        self.register(SELENIUM_EMAIL, SELENIUM_PASSWORD, SELENIUM_PASSWORD)
        self.wait_for_element_present("logout_link")
        self.logout()

        # try to register again with same email (using a different phone)
        self.wait_for_element_and_click_at("join_link")
        self.wait_for_element_present("local_phone")
        self.validate_phone(phone="0000000000")
        self.wait_for_element_and_type("email", SELENIUM_EMAIL)
        self.register(SELENIUM_EMAIL, SELENIUM_PASSWORD, SELENIUM_PASSWORD, dont_click=True)
        self.wait_for_text_present(u'דוא"ל כבר רשום')

    def test_autocomplete(self):
        logging.info("testing autocomplete")
        sel = self.selenium
        sel.open("/")

        sel.type_keys("id_from_raw", u"אל")
        self.wait_for_autocomplete_and_click(u"//html/body/ul/li/a[. = \"אלנבי 1, תל אביב יפו\"]")

        sel.type_keys("id_to_raw", u"הרצ")
        self.wait_for_autocomplete_and_click(u"//html/body/ul/li/a[. = \"הרצל 1, תל אביב יפו\"]")

        self.wait_for_text_present(u"מחיר נסיעה משוער")

    def test_order_no_service(self):
        logging.info("testing order with no service")
        sel = self.selenium
        self.login_as_selenium()

        # order where is no service
        address = u"אודם 1, אלפי מנשה"
        self.book_order(address)
        self.assertTrue(sel.get_text("ui-dialog-title-dialog") == u"לא ניתן להזמין נסיעה זו")
        sel.click("ok")
        
    def test_order_as_passenger(self):
        logging.info("testing order as passenger")
        sel = self.selenium
        self.login_as_selenium()

        sel.open("/")
        self.book_order(SELENIUM_ADDRESS)
        self.assertTrue(sel.get_text("ui-dialog-title-dialog") == u"הזמנתך התקבלה!")
        sel.click("ok")

        # ordering again is forbidden, too soon
        sel.open("/")
        self.book_order(SELENIUM_ADDRESS)
        self.assertTrue(sel.get_text("ui-dialog-title-dialog") == u"לא ניתן להזמין נסיעה זו")
        sel.click("ok")

    def test_order_as_unregistered(self):
        logging.info("testing order as unregistered")
        sel = self.selenium

        # create test station
        sel.open(reverse('testing.setup_testing_env.create_selenium_test_station'))

        sel.open("/")
        self.book_order(SELENIUM_ADDRESS)
        self.validate_phone()
        time.sleep(1)
        self.assertTrue(sel.get_text("ui-dialog-title-dialog") == u"הזמנתך התקבלה!")
        time.sleep(5)
        self.register()
        self.wait_for_element_present("logout_link")
        self.logout()

    def test_station_side(self):
        logging.info("testing station side")
        sel = self.selenium
        sel.open(reverse('testing.setup_testing_env.create_selenium_test_data'))
        sel.open("/stations")

        sel.type("id_username", SELENIUM_STATION_USER_NAME)
        sel.type("id_password", SELENIUM_PASSWORD)
        sel.click("id_station_login")

        # order history page
        self.wait_for_element_and_click_at("//a[@href='#history']")
        self.assertTrue(sel.is_text_present(u"היכל נוקיה"))

        # profile page
        sel.click("//a[@href='#profile']")
        self.assertTrue(sel.get_eval("window.jQuery('#id_name').val()") == u'selenium_station')
        self.assertTrue(sel.get_eval("window.jQuery('#id_address').val()") == SELENIUM_ADDRESS)
        self.assertTrue(sel.get_eval("window.jQuery('#id_phones-0-local_phone').val()") == SELENIUM_PHONE)
        # add phone
        sel.type_keys("id_phones-0-local_phone", SELENIUM_PHONE)
        sel.click("id_save_station_profile") # bug - can't save form

        # install workstations page
        sel.click("//a[@href='#download']")


    def tearDown(self):
        self.selenium.open(reverse('testing.setup_testing_env.destroy_selenium_test_data'))
        self.selenium.stop()
        self.assertEqual([], self.verificationErrors)
