# -*- coding: utf-8 -*-

# don't forget to run a selenium server while running integration tests.
# See: http://seleniumhq.org/docs/05_selenium_rc.html#installation
from django.http import HttpRequest
from django.test import TestCase
from django.core.urlresolvers import reverse
from selenium import selenium
from selenium_helper import SelemiumHelper
import setup_testing_env
from common.models import Country
from ordering.passenger_controller import send_sms_verification, SELENIUM_TEST_KEY

APPLICATION_UNDER_TEST = "http://localhost:8000"
#APPLICATION_UNDER_TEST = "http://3.latest.waybetter-app.appspot.com/"

SELENIUM_USER_NAME = setup_testing_env.SELENIUM_USER_NAME
SELENIUM_PASSWORD = setup_testing_env.SELENIUM_USER_NAME

class SeleniumTests(TestCase, SelemiumHelper):
    fixtures = ['countries.yaml']
    selenium = None

    def setUp(self):
        self.verificationErrors = []
        self.selenium = selenium("localhost", 4444, "*firefox", APPLICATION_UNDER_TEST)
        self.selenium.start()

    def test_login_logout(self):
        self.login_as_selenium()
        self.logout()

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
        # bug - double click is needed
        sel.click("history_header_label_1")
        sel.click("history_header_label_1")
        self.wait_for_text(u"גאולה 1 תל אביב", "//div[@id='orders_history_grid']/table/tbody/tr[2]/td[2]")

#    def test_join(self):
#        sel = self.selenium
#        sel.open("/")
#        sel.click("join_link")
#        self.wait_for_element_present("local_phone")
#
#        # simulate code sent by sms to the user
#        request = HttpRequest
#        request.mobile = False
#        request.session = {}
#        israel_id = int(Country.objects.get(code="IL").id)
#        request.POST={"country": israel_id,
#                      "local_phone": "0001234567"
#        }
#        response = send_sms_verification(request, testKey=SELENIUM_TEST_KEY)
#
#        sel.type_keys("local_phone", "0001234567")
#        sel.click("local_phone")
#
#        self.wait_for_element_present("css=div.sms-button")
#        sel.click("css=div.sms-button")
#
#        sel.type_keys("verification_code", str(response.content))
#        sel.click("verification_code")
#
#        submit_code_btn_id = "//form[@id='phone_verification_form']/fieldset/div[2]"
#        self.wait_for_element_present(submit_code_btn_id)
#        sel.click(submit_code_btn_id)



    def tearDown(self):
        self.selenium.open(reverse('testing.setup_testing_env.destroy_selenium_test_data'))
        self.selenium.stop()
        self.assertEqual([], self.verificationErrors)
