from django.utils import translation
from django.utils.translation import ugettext as _
from transliterate import Transliteration, TransliterationError
from common.util import is_in_english
from common.geocode import geocode

import settings
import logging
import re

def translate_to_lang(msg, lang_code):
    current_lang = translation.get_language()
    translation.activate(lang_code)
    msg = _(msg)
    translation.activate(current_lang)
    return msg

def translate_to_ws_lang(msg, ws):
    ws_lang_code = settings.LANGUAGES[ws.station.language][0]
    return translate_to_lang(msg, ws_lang_code)

def translate_address_for_ws(ws, order, address_type):
    """
    Translate the pickup address to the workstation's language. Currently only English to Hebrew are supported.
    
    @param ws: C{WorkStation}
    @param order: C{Order}
    @param address_type: either 'from' or 'to'
    @return: the translated address
    """
    
    address = getattr(order, "%s_raw" % address_type)

    order_lang_code = 'en' if is_in_english(address) else 'he'
    ws_lang_code = settings.LANGUAGES[ws.station.language][0]

    if order_lang_code == 'en' and ws_lang_code == 'he':
        try:
            address = transliterate_english_order_to_hebrew(order, address_type=address_type)
        except TransliterationError:
            logging.error("Transliteration error for %s" % address)

    return address

def transliterate_english_order_to_hebrew(order, address_type):
    """
    Translate English order to Hebrew by transliterating the street name and geocoding the result, looking for a match.
    If no match is found, the transliterated result is returned.
    """

    street_address = getattr(order, "%s_street_address" % address_type)
    house_number = getattr(order, "%s_house_number" % address_type) # or int(re.search("\d+", getattr(order, "%s_raw" % address_type)).group(0))
    city = getattr(order, "%s_city" % address_type)
    lat = getattr(order, "%s_lat" % address_type)
    lon = getattr(order, "%s_lon" % address_type)

    # transliterate English street name to Hebrew
    logging.info("queying google transliteration for %s" % street_address)
    hebrew_transliterator = Transliteration('iw')
    hebrew_street_address = hebrew_transliterator.getTransliteration(street_address.replace("'", ""))
    logging.info("transliteration returned %s" % hebrew_street_address)

    hebrew_address = hebrew_street_address
    if house_number:
        hebrew_address = u"%s %d" % (hebrew_street_address, house_number)

    # geocode transliterated address, and look for one with matching lon, lat
    results = geocode(hebrew_address, constrain_to_city=city)

    for result in results:
        if float(result["lat"]) == lat and float(result["lon"]) == lon:
            logging.info("telmap found a match")
            return u"%s %s, %s" % (result["street_address"], result["house_number"], result["city"])

    # try again without constrain to city
    hebrew_address = u"%s, %s" % (hebrew_address, city.name)
    results = geocode(hebrew_address)

    for result in results:
        if float(result["lat"]) == lat and float(result["lon"]) == lon:
            logging.info("telmap found a match")
            return u"%s %s, %s" % (result["street_address"], result["house_number"], result["city"])

    logging.info("telmap DID NOT find a match")
    return order.from_raw
