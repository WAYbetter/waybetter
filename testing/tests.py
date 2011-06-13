# -*- coding: utf-8 -*-

# don't forget to run a selenium server while running integration tests, see: http://seleniumhq.org/docs/05_selenium_rc.html#installation
# to use jquery locators you must modify RemoteRunner.html , see http://stackoverflow.com/questions/2814007/how-to-i-add-a-jquery-locators-to-selenium-remote-control

#import setup_testing_env
from django.test import TestCase
from django.core.urlresolvers import reverse
from selenium import selenium
from selenium_helper import SelemiumHelper, SELENIUM_PASSWORD, SELENIUM_EMAIL, SELENIUM_ADDRESS, SELENIUM_PHONE, SELENIUM_STATION_USER_NAME, SELENIUM_NEW_USER_NAME, SELENIUM_UNREGISTERED_PHONE
import time
import logging

APPLICATION_UNDER_TEST = "http://localhost:8000/"
#APPLICATION_UNDER_TEST = "http://3.latest.waybetter-app.appspot.com/"
#APPLICATION_UNDER_TEST = "http://www.waybetter.com/"

SOCIAL_GOOGLE = ["css=.google", "Google Accounts", "Email", "Passwd", "signIn"]
SOCIAL_FACEBOOK = ["css=.facebook", "Login | Facebook", "email", "pass", "login"]
SOCIAL_TWITTER = ["css=.twitter", "Twitter", "username_or_email", "password", "allow"]
FIREFOX_LOCATION = '*firefox'

class SeleniumTests(TestCase, SelemiumHelper):
    fixtures = ['countries.yaml']
    selenium = None

    def setUp(self):
        self.verificationErrors = []
        self.selenium = selenium("localhost", 4444, FIREFOX_LOCATION, APPLICATION_UNDER_TEST)
#        self.selenium.set_timeout(30000) # milisecond
        self.selenium.set_speed(250) # milisecond
        self.selenium.start()
        self.selenium.window_maximize()

    def test_login(self):
        logging.info("testing login")
        sel = self.selenium
        sel.open("/")
        self.wait_for_element_and_click_at("login_link")

        self.login(wrong_username=True)
        self.wait_for_text(None , "login_error")
        sel.get_eval('window.jQuery("#login_error").text("")')

        self.login(wrong_password=True)
        self.wait_for_text(None , "login_error")

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
        self.social_login(*SOCIAL_GOOGLE)

        # Facebook and Twitter only allow waybetter.com requests
        if APPLICATION_UNDER_TEST == 'http://www.waybetter.com/':
            self.social_login(*SOCIAL_FACEBOOK)
            self.social_login(*SOCIAL_TWITTER)

    def test_passenger_home(self):
        logging.info("testing passenger home")
        sel = self.selenium
        self.login_as_selenium()

        required_elements = ["history_tab_btn", "profile_tab_btn", "stations_tab_btn", "mobile_tab_btn", "id_from_raw",
                             "id_to_raw", "order_button", "feedback_peal"]

        for element in required_elements:
            self.assertTrue(sel.is_element_present(element))

    def test_change_credentials(self):
        logging.info("testing change credentials")
        sel = self.selenium
        new_password = "new_password"
        new_email = SELENIUM_NEW_USER_NAME

        sel.open(reverse('testing.setup_testing_env.create_selenium_test_data'))
        sel.open("/")

        self.wait_for_element_and_click_at("login_link")
        time.sleep(1)
        self.wait_for_element_and_click_at("cant_login_link")

        # enter unregistered phone - forbidden
        self.wait_for_element_and_type("local_phone", SELENIUM_UNREGISTERED_PHONE)
        self.wait_for_text_present(u"הטלפון לא רשום")

        # change password and email and login using new credentials
        sel.open("/")
        self.change_credentials(new_email=new_email, new_password=new_password)
        self.wait_for_element_present("logout_link")
        self.logout()

        self.wait_for_element_and_click_at("login_link")
        self.login(username=new_email, password=new_password)
        self.wait_for_element_present("logout_link")
        self.logout()

        # use a social account (Google)
        self.change_credentials(new_email="", new_password="", dont_click=True)
        self.social_authentication(*SOCIAL_GOOGLE)
        self.wait_for_element_and_click_at("profile_tab_btn")
        self.wait_for_text(SELENIUM_PHONE, "current_phone")
        self.assertFalse(sel.is_element_present("id_password")) # check we indeed have social user
        self.logout()

        # change back to a waybetter account
        self.change_credentials(new_email=new_email, new_password=new_password)
        self.wait_for_element_and_click_at("profile_tab_btn")
        self.wait_for_text(SELENIUM_PHONE, "current_phone")
        self.wait_for_element_present("id_password")
        self.logout()

    def test_change_password(self):
        logging.info("testing change password")
        sel = self.selenium
        self.login_as_selenium()

        # change password and logout
        self.wait_for_element_and_click_at("profile_tab_btn")
        self.wait_for_element_and_type("id_password", "newpassword")
        self.type_and_click("id_password2", "newpassword")
        sel.click("save_profile_changes")
        self.wait_for_text_present(u"השינויים נשמרו בהצלחה")

        sel.open("/")
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
        new_phone = SELENIUM_UNREGISTERED_PHONE

        self.login_as_selenium()
        self.wait_for_element_and_click_at("profile_tab_btn")
        self.wait_for_element_present("change_phone")

        time.sleep(1)

        sel.click("change_phone")
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

        self.wait_for_text(u"היכל נוקיה", "//div[@id='orders_history_grid']/table/tbody/tr[2]/td[2]")
        # choose address from history
        sel.click("id_from_raw")
        time.sleep(1)
        sel.mouse_down("//div[@id='orders_history_grid']/table/tbody/tr[2]/td[2]")
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
        self.validate_phone(phone=SELENIUM_UNREGISTERED_PHONE)
        self.wait_for_element_and_type("email", SELENIUM_EMAIL)
        self.register(SELENIUM_EMAIL, SELENIUM_PASSWORD, SELENIUM_PASSWORD, dont_click=True)
        self.wait_for_text_present(u'דוא"ל כבר רשום')

    def test_autocomplete(self):
        logging.info("testing autocomplete")
        sel = self.selenium
        sel.open("/")

        sel.click("id_from_raw")
        sel.type_keys("id_from_raw", u"אל 1 תא")
        self.wait_for_autocomplete_and_click(u"//html/body/ul/li/a[. = \"אלנבי 1, תל אביב יפו\"]")

        sel.click("id_to_raw")
        sel.type_keys("id_to_raw", u"הרצ 1 תא")
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
        self.wait_for_text(u"הזמנתך התקבלה!", "ui-dialog-title-dialog")
        time.sleep(5)
        self.register()
        self.wait_for_element_present("logout_link")
        self.logout()

    def test_station_subdomain(self):
        logging.info("testing station subdomain")

        # must use a new selenium instance (same origin policy)
        sel = selenium("localhost", 4444, "*firefox", "http://ny.taxiapp.co.il")
        sel.start()
        sel.open("/")
        self.assertTrue(sel.is_element_present("//a[@href='http://www.ny-taxi.co.il']"))
        sel.stop()

    def test_station_side(self):
        logging.info("testing station side")
        sel = self.selenium
        sel.open(reverse('testing.setup_testing_env.create_selenium_test_data'))
        sel.open("/stations")

        # test login
        self.wait_for_element_present("id_station_login")
        sel.type("id_username", SELENIUM_STATION_USER_NAME)
        sel.type("id_password", SELENIUM_PASSWORD)
        sel.click("id_station_login")

        # order history page
        self.wait_for_element_and_click_at("//a[@href='#history']")
        self.wait_for_text_present(u"היכל נוקיה")

        # profile page
        sel.click("//a[@href='#profile']")
        self.wait_for_element_present("id_email")

        data = {
            # id                       : (old_val, new_val),
            'id_name'                 : (u'selenium_station', u'new_selenium_station'),
            'id_address'              : (SELENIUM_ADDRESS, u"new address"),
            'id_number_of_taxis'      : ('5', '6'),
            'id_website_url'          : ('http://selenium.waybetter.com','http://selenium.waybetter.co.il'),
            'id_email'                : ('selenium_station@waybetter.com', 'selenium_station@waybetter.co.il'),
            'id_description'          : ('','new description'),
            'id_phones-0-local_phone' : (SELENIUM_PHONE, '123')
        }

        for id in data.keys():
            self.assertTrue(sel.get_eval("window.jQuery('#%s').val()"%id) == data[id][0])
            sel.type(id, data[id][1])

        sel.click("id_save_station_profile")
        # TODO_WB: check if no errors where reported

#        # add phone
#        sel.type_keys("id_phones-0-local_phone", SELENIUM_PHONE)

        # change password

        # install workstations page
        sel.click("//a[@href='#download']")


    def tearDown(self):
        self.selenium.open(reverse('testing.setup_testing_env.destroy_selenium_test_data'))
        self.selenium.stop()
        self.assertEqual([], self.verificationErrors)
