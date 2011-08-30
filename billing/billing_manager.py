from datetime import datetime
import logging
from google.appengine.api.urlfetch import fetch
from common.util import get_unique_id

TRANSACTION_URL = "https://cgmpiuat.creditguard.co.il/CGMPI_Server/CreateTransactionExtended"
ALL_QUERY_FIELDS = {
    "MID"					:               "",
    "userName"				:				"",
    "password"				:				"",
    "mainTerminalNumber"	:				"",
    "terminal"				:				"",
    "uniqueID"				:				"",
    "amount"				:				"",
    "currency"				:				"",
    "transactionType"		:				"",
    "creditType"			:				"",
    "transactionCode"		:				"",
    "authNumber"			:				"",
    "numberOfPayments"		:				"",
    "firstPayment"			:				"",
    "periodicalPayment"		:				"",
    "validationType"		:				"",
    "dealerNumber"			:				"",
    "description"			:				"",
    "email"					:				"",
    "langID"				:				"",
    "timestamp"				:				"",
    "clientIP"				:				"",
    "xRem"					:				"",
    "userData1"				:				"",
    "userData2"				:				"",
    "userData3"				:				"",
    "userData4"				:				"",
    "userData5"				:				"",
    "userData6"				:				"",
    "userData7"				:				"",
    "userData8"				:				"",
    "userData9"				:				"",
    "userData10"			:				"",
    "saleDetailsMAC"		:				""
}


#def bill_passenger(passenger, ride, amount):
#    transaction = BillingTransaction(passenger=passenger, amount=amount, ride=ride)
#    transaction.commit()

def get_transaction_id(amount=0):
    data = ALL_QUERY_FIELDS.copy()
    data.update({
        "MID":              112,
        "userName":         "wiibet",
        "password":         "312.2BE#e704",
        "terminal":         "0962831",
        "uniqueID":         get_unique_id(),
        "amount":           amount,
        "currency":         "ILS",
        "transactionType":  "Debit",
        "creditType":       "RegularCredit",
        "transactionCode":  "Phone",
        "authNumber":       1234567, # used only for testing
        "validationType":   "Normal",
        "langID":           "EN",
        "timestamp":        datetime.now().replace(microsecond=0).isoformat() #"2011-10-22T15:44:53" #default_tz_now().isoformat()
    })

    # encode data without using urlencode
    data = "&".join(["%s=%s" % i for i in data.items()])
    
    logging.info(data)
    res = fetch(TRANSACTION_URL, method="POST", payload=data, deadline=10)
    if res.content.startswith("--"):
        logging.error("No transaction ID received: %s" % res.content)
        return None

    return res.content
