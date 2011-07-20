from common.decorators import internal_task_on_queue, catch_view_exceptions
from common.models import Country
from common.util import has_related_objects, url_with_querystring, get_unique_id, notify_by_email
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api import xmpp
from google.appengine.api.labs.taskqueue import DuplicateTaskNameError, TaskAlreadyExistsError, TombstonedTaskError
from google.appengine.api.labs.taskqueue import taskqueue
from ordering.models import WorkStation, Order, Passenger, OrderAssignment, SharedRide
from settings import ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL, INIT_TOKEN
import logging

# DeadlineExceededError can live in two different places
try:
    # When deployed
    from google.appengine.runtime import DeadlineExceededError
except ImportError:
    from google.appengine.runtime.apiproxy_errors import DeadlineExceededError
    # In the development server

from google.appengine.ext import deferred

@staff_member_required
def run_maintenance_task(request):
    base_name = 'maintenance-task'
    name = request.GET.get("name", base_name)
    task = taskqueue.Task(url=reverse(maintenance_task), name=name)
    q = taskqueue.Queue('maintenance')
    response = HttpResponse("Task Added")
    try:
        q.add(task)
    except TombstonedTaskError:
        response = HttpResponseRedirect(
            url_with_querystring(reverse(run_maintenance_task), name="%s-%s" % (base_name, get_unique_id())))
    except TaskAlreadyExistsError:
        response = HttpResponse("Task not added: TaskAlreadyExistsError")
    except DuplicateTaskNameError:
        response = HttpResponse("Task not added: DuplicateTaskNameError")

    return response


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("maintenance")
def maintenance_task(request):
    try:
        do_task()
        return HttpResponse("Done")
    except Exception, e:
        logging.error("Failed during task: %s" % e)
        return HttpResponse("Failed")



def do_task():
    delete_shared_orders()

#    generate_passengers_with_non_existing_users()
#    generate_dead_users_list()

def delete_shared_orders():
    rides = SharedRide.objects.all()
    for ride in rides:
        logging.info("deleting ride %d" % ride.id)
        ride.orders.all().delete()
        ride.points.all().delete()
        ride.delete()

def denormalize_order_assignments():
    for oa in OrderAssignment.objects.all():

        if oa.dn_from_raw:
            continue # is normalized
            
        if hasattr(oa, 'business_name'):
            oa.dn_business_name = oa.business_name
            oa.business_name = None

        try:
            oa.save()
            logging.info("denormalizing assignment [%d]" % oa.id)
        except Order.DoesNotExist:
            oa.delete()
        except Passenger.DoesNotExist:
            pass
        except Exception, e:
            logging.error("FAILED denormalizing assignment [%d]: %s" % (oa.id, e))
            
    logging.info("task finished")


def reset_password():
    names = ["amir_station_1", "amir_station_1_workstation_1", "amir_station_1_workstation_2", "amir_station_2", "amir_station_2_workstation_1", "amir_station_2_workstation_2"]
    for name in names:
        user = User.objects.get(username=name)
        user.set_password(name)
        user.save()


def generate_dead_users_list():
    list = ""
    for user in User.objects.all():
        if has_related_objects(user):
            user_link = '<a href="http://www.waybetter.com/admin/auth/user/%d/">%d</a>' % (user.id, user.id)
            list += "user [%s]: %s<br/>" % (user.username, user_link)

    notify_by_email("Dead users list", html=list)


def generate_passengers_with_non_existing_users():
    passengers_list = ""
    for passenger in Passenger.objects.all():
        try:
            passenger.user
        except:
            passenger_link = '<a href="http://www.waybetter.com/admin/ordering/passenger/%d/">%d</a>' % (
                passenger.id, passenger.id)
            passengers_list += "passenger [%s]: %s<br/>" % (passenger.phone, passenger_link)

    notify_by_email("Passengers linked to users which do not exist", html=passengers_list)


def fix_orders():
    import re

    for order in Order.objects.all():
        if not getattr(order, "from_house_number"):
            logging.info("processing order %d" % order.id)
            numbers = re.findall(r"\b(\d+)\b", order.from_raw)
            house_number = numbers[0] if numbers else 1
            order.from_house_number = house_number
            try:
                order.save()
            except Exception, e:
                logging.error("Could not save order: %d: %s" % (order.id, e.message))


def setup(request):
    if "token" in request.GET:
        if request.GET["token"] == INIT_TOKEN:
            try:
                admin = User.objects.get(username=ADMIN_USERNAME)
                admin.set_password(ADMIN_PASSWORD)
                admin.email = ADMIN_EMAIL
                admin.save()
                return HttpResponse('Admin reset!')
            except User.DoesNotExist:
                u = User()
                u.username = ADMIN_USERNAME
                u.set_password(ADMIN_PASSWORD)
                u.email = ADMIN_EMAIL
                u.is_active = True
                u.is_staff = True
                u.is_superuser = True
                u.save()
                return HttpResponse('Admin created!')
            except User.MultipleObjectsReturned:
                return HttpResponse('More than one admin.')

        if request.GET["token"] == 'send_invites':
            count = 0
            for ws in WorkStation.objects.all():
                count = count + 1
                xmpp.send_invite(ws.im_user)

            return HttpResponse('Sent invites to %d work station' % count)

    return HttpResponse('Wrong usage! (pass token)')


@login_required
def test_channel(request):
    from google.appengine.api import channel

    logging.info("Create channel: " + request.user.username)
    c = channel.create_channel(request.user.username)
    return HttpResponse("channel created")


def init_countries(request, start=0):
    countries_created = do_init(start)
    return HttpResponse("%d countries created" % countries_created)

#    if Country.objects.all().count() > 1:
#        from django.core.serializers import serialize
#        cc = Country.objects.all()
#        return HttpResponse(serialize("json", cc))

def do_init(start=0):
    countries = [{"code": "IL", "dial_code": "+972", "name": "Israel"},
            {"code": "AF", "dial_code": "+93", "name": "Afghanistan"},
            {"code": "AL", "dial_code": "+355", "name": "Albania"},
            {"code": "DZ", "dial_code": "+213", "name": "Algeria"},
            {"code": "AS", "dial_code": "+1 684", "name": "American Samoa"},
            {"code": "AD", "dial_code": "+376", "name": "Andorra"},
            {"code": "AO", "dial_code": "+244", "name": "Angola"},
            {"code": "AI", "dial_code": "+1 264", "name": "Anguilla"},
            {"code": "AG", "dial_code": "+1 268", "name": "Antigua and Barbuda"},
            {"code": "AR", "dial_code": "+54", "name": "Argentina"},
            {"code": "AM", "dial_code": "+374", "name": "Armenia"},
            {"code": "AW", "dial_code": "+297", "name": "Aruba"},
            {"code": "AU", "dial_code": "+61", "name": "Australia"},
            {"code": "AT", "dial_code": "+43", "name": "Austria"},
            {"code": "AZ", "dial_code": "+994", "name": "Azerbaijan"},
            {"code": "BS", "dial_code": "+1 242", "name": "Bahamas"},
            {"code": "BH", "dial_code": "+973", "name": "Bahrain"},
            {"code": "BD", "dial_code": "+880", "name": "Bangladesh"},
            {"code": "BB", "dial_code": "+1 246", "name": "Barbados"},
            {"code": "BY", "dial_code": "+375", "name": "Belarus"},
            {"code": "BE", "dial_code": "+32", "name": "Belgium"},
            {"code": "BZ", "dial_code": "+501", "name": "Belize"},
            {"code": "BJ", "dial_code": "+229", "name": "Benin"},
            {"code": "BM", "dial_code": "+1 441", "name": "Bermuda"},
            {"code": "BT", "dial_code": "+975", "name": "Bhutan"},
            {"code": "BA", "dial_code": "+387", "name": "Bosnia and Herzegovina"},
            {"code": "BW", "dial_code": "+267", "name": "Botswana"},
            {"code": "BR", "dial_code": "+55", "name": "Brazil"},
            {"code": "IO", "dial_code": "+246", "name": "British Indian Ocean Territory"},
            {"code": "BG", "dial_code": "+359", "name": "Bulgaria"},
            {"code": "BF", "dial_code": "+226", "name": "Burkina Faso"},
            {"code": "BI", "dial_code": "+257", "name": "Burundi"},
            {"code": "KH", "dial_code": "+855", "name": "Cambodia"},
            {"code": "CM", "dial_code": "+237", "name": "Cameroon"},
            {"code": "CA", "dial_code": "+1", "name": "Canada"},
            {"code": "CV", "dial_code": "+238", "name": "Cape Verde"},
            {"code": "KY", "dial_code": "+ 345", "name": "Cayman Islands"},
            {"code": "CF", "dial_code": "+236", "name": "Central African Republic"},
            {"code": "TD", "dial_code": "+235", "name": "Chad"},
            {"code": "CL", "dial_code": "+56", "name": "Chile"},
            {"code": "CN", "dial_code": "+86", "name": "China"},
            {"code": "CX", "dial_code": "+61", "name": "Christmas Island"},
            {"code": "CO", "dial_code": "+57", "name": "Colombia"},
            {"code": "KM", "dial_code": "+269", "name": "Comoros"},
            {"code": "CG", "dial_code": "+242", "name": "Congo"},
            {"code": "CK", "dial_code": "+682", "name": "Cook Islands"},
            {"code": "CR", "dial_code": "+506", "name": "Costa Rica"},
            {"code": "HR", "dial_code": "+385", "name": "Croatia"},
            {"code": "CU", "dial_code": "+53", "name": "Cuba"},
            {"code": "CY", "dial_code": "+537", "name": "Cyprus"},
            {"code": "CZ", "dial_code": "+420", "name": "Czech Republic"},
            {"code": "DK", "dial_code": "+45", "name": "Denmark"},
            {"code": "DJ", "dial_code": "+253", "name": "Djibouti"},
            {"code": "DM", "dial_code": "+1 767", "name": "Dominica"},
            {"code": "DO", "dial_code": "+1 849", "name": "Dominican Republic"},
            {"code": "EC", "dial_code": "+593", "name": "Ecuador"},
            {"code": "EG", "dial_code": "+20", "name": "Egypt"},
            {"code": "SV", "dial_code": "+503", "name": "El Salvador"},
            {"code": "GQ", "dial_code": "+240", "name": "Equatorial Guinea"},
            {"code": "ER", "dial_code": "+291", "name": "Eritrea"},
            {"code": "EE", "dial_code": "+372", "name": "Estonia"},
            {"code": "ET", "dial_code": "+251", "name": "Ethiopia"},
            {"code": "FO", "dial_code": "+298", "name": "Faroe Islands"},
            {"code": "FJ", "dial_code": "+679", "name": "Fiji"},
            {"code": "FI", "dial_code": "+358", "name": "Finland"},
            {"code": "FR", "dial_code": "+33", "name": "France"},
            {"code": "GF", "dial_code": "+594", "name": "French Guiana"},
            {"code": "PF", "dial_code": "+689", "name": "French Polynesia"},
            {"code": "GA", "dial_code": "+241", "name": "Gabon"},
            {"code": "GM", "dial_code": "+220", "name": "Gambia"},
            {"code": "GE", "dial_code": "+995", "name": "Georgia"},
            {"code": "DE", "dial_code": "+49", "name": "Germany"},
            {"code": "GH", "dial_code": "+233", "name": "Ghana"},
            {"code": "GI", "dial_code": "+350", "name": "Gibraltar"},
            {"code": "GR", "dial_code": "+30", "name": "Greece"},
            {"code": "GL", "dial_code": "+299", "name": "Greenland"},
            {"code": "GD", "dial_code": "+1 473", "name": "Grenada"},
            {"code": "GP", "dial_code": "+590", "name": "Guadeloupe"},
            {"code": "GU", "dial_code": "+1 671", "name": "Guam"},
            {"code": "GT", "dial_code": "+502", "name": "Guatemala"},
            {"code": "GN", "dial_code": "+224", "name": "Guinea"},
            {"code": "GW", "dial_code": "+245", "name": "Guinea-Bissau"},
            {"code": "GY", "dial_code": "+595", "name": "Guyana"},
            {"code": "HT", "dial_code": "+509", "name": "Haiti"},
            {"code": "HN", "dial_code": "+504", "name": "Honduras"},
            {"code": "HU", "dial_code": "+36", "name": "Hungary"},
            {"code": "IS", "dial_code": "+354", "name": "Iceland"},
            {"code": "IN", "dial_code": "+91", "name": "India"},
            {"code": "ID", "dial_code": "+62", "name": "Indonesia"},
            {"code": "IQ", "dial_code": "+964", "name": "Iraq"},
            {"code": "IE", "dial_code": "+353", "name": "Ireland"},
            {"code": "IL", "dial_code": "+972", "name": "Israel"},
            {"code": "IT", "dial_code": "+39", "name": "Italy"},
            {"code": "JM", "dial_code": "+1 876", "name": "Jamaica"},
            {"code": "JP", "dial_code": "+81", "name": "Japan"},
            {"code": "JO", "dial_code": "+962", "name": "Jordan"},
            {"code": "KZ", "dial_code": "+7 7", "name": "Kazakhstan"},
            {"code": "KE", "dial_code": "+254", "name": "Kenya"},
            {"code": "KI", "dial_code": "+686", "name": "Kiribati"},
            {"code": "KW", "dial_code": "+965", "name": "Kuwait"},
            {"code": "KG", "dial_code": "+996", "name": "Kyrgyzstan"},
            {"code": "LV", "dial_code": "+371", "name": "Latvia"},
            {"code": "LB", "dial_code": "+961", "name": "Lebanon"},
            {"code": "LS", "dial_code": "+266", "name": "Lesotho"},
            {"code": "LR", "dial_code": "+231", "name": "Liberia"},
            {"code": "LI", "dial_code": "+423", "name": "Liechtenstein"},
            {"code": "LT", "dial_code": "+370", "name": "Lithuania"},
            {"code": "LU", "dial_code": "+352", "name": "Luxembourg"},
            {"code": "MG", "dial_code": "+261", "name": "Madagascar"},
            {"code": "MW", "dial_code": "+265", "name": "Malawi"},
            {"code": "MY", "dial_code": "+60", "name": "Malaysia"},
            {"code": "MV", "dial_code": "+960", "name": "Maldives"},
            {"code": "ML", "dial_code": "+223", "name": "Mali"},
            {"code": "MT", "dial_code": "+356", "name": "Malta"},
            {"code": "MH", "dial_code": "+692", "name": "Marshall Islands"},
            {"code": "MQ", "dial_code": "+596", "name": "Martinique"},
            {"code": "MR", "dial_code": "+222", "name": "Mauritania"},
            {"code": "MU", "dial_code": "+230", "name": "Mauritius"},
            {"code": "YT", "dial_code": "+262", "name": "Mayotte"},
            {"code": "MX", "dial_code": "+52", "name": "Mexico"},
            {"code": "MC", "dial_code": "+377", "name": "Monaco"},
            {"code": "MN", "dial_code": "+976", "name": "Mongolia"},
            {"code": "ME", "dial_code": "+382", "name": "Montenegro"},
            {"code": "MS", "dial_code": "+1664", "name": "Montserrat"},
            {"code": "MA", "dial_code": "+212", "name": "Morocco"},
            {"code": "MM", "dial_code": "+95", "name": "Myanmar"},
            {"code": "NA", "dial_code": "+264", "name": "Namibia"},
            {"code": "NR", "dial_code": "+674", "name": "Nauru"},
            {"code": "NP", "dial_code": "+977", "name": "Nepal"},
            {"code": "NL", "dial_code": "+31", "name": "Netherlands"},
            {"code": "AN", "dial_code": "+599", "name": "Netherlands Antilles"},
            {"code": "NC", "dial_code": "+687", "name": "New Caledonia"},
            {"code": "NZ", "dial_code": "+64", "name": "New Zealand"},
            {"code": "NI", "dial_code": "+505", "name": "Nicaragua"},
            {"code": "NE", "dial_code": "+227", "name": "Niger"},
            {"code": "NG", "dial_code": "+234", "name": "Nigeria"},
            {"code": "NU", "dial_code": "+683", "name": "Niue"},
            {"code": "NF", "dial_code": "+672", "name": "Norfolk Island"},
            {"code": "MP", "dial_code": "+1 670", "name": "Northern Mariana Islands"},
            {"code": "NO", "dial_code": "+47", "name": "Norway"},
            {"code": "OM", "dial_code": "+968", "name": "Oman"},
            {"code": "PK", "dial_code": "+92", "name": "Pakistan"},
            {"code": "PW", "dial_code": "+680", "name": "Palau"},
            {"code": "PA", "dial_code": "+507", "name": "Panama"},
            {"code": "PG", "dial_code": "+675", "name": "Papua New Guinea"},
            {"code": "PY", "dial_code": "+595", "name": "Paraguay"},
            {"code": "PE", "dial_code": "+51", "name": "Peru"},
            {"code": "PH", "dial_code": "+63", "name": "Philippines"},
            {"code": "PL", "dial_code": "+48", "name": "Poland"},
            {"code": "PT", "dial_code": "+351", "name": "Portugal"},
            {"code": "PR", "dial_code": "+1 939", "name": "Puerto Rico"},
            {"code": "QA", "dial_code": "+974", "name": "Qatar"},
            {"code": "RO", "dial_code": "+40", "name": "Romania"},
            {"code": "RW", "dial_code": "+250", "name": "Rwanda"},
            {"code": "WS", "dial_code": "+685", "name": "Samoa"},
            {"code": "SM", "dial_code": "+378", "name": "San Marino"},
            {"code": "SA", "dial_code": "+966", "name": "Saudi Arabia"},
            {"code": "SN", "dial_code": "+221", "name": "Senegal"},
            {"code": "RS", "dial_code": "+381", "name": "Serbia"},
            {"code": "SC", "dial_code": "+248", "name": "Seychelles"},
            {"code": "SL", "dial_code": "+232", "name": "Sierra Leone"},
            {"code": "SG", "dial_code": "+65", "name": "Singapore"},
            {"code": "SK", "dial_code": "+421", "name": "Slovakia"},
            {"code": "SI", "dial_code": "+386", "name": "Slovenia"},
            {"code": "SB", "dial_code": "+677", "name": "Solomon Islands"},
            {"code": "ZA", "dial_code": "+27", "name": "South Africa"},
            {"code": "GS", "dial_code": "+500", "name": "South Georgia and the South Sandwich Islands"},
            {"code": "ES", "dial_code": "+34", "name": "Spain"},
            {"code": "LK", "dial_code": "+94", "name": "Sri Lanka"},
            {"code": "SD", "dial_code": "+249", "name": "Sudan"},
            {"code": "SR", "dial_code": "+597", "name": "Suriname"},
            {"code": "SZ", "dial_code": "+268", "name": "Swaziland"},
            {"code": "SE", "dial_code": "+46", "name": "Sweden"},
            {"code": "CH", "dial_code": "+41", "name": "Switzerland"},
            {"code": "TJ", "dial_code": "+992", "name": "Tajikistan"},
            {"code": "TH", "dial_code": "+66", "name": "Thailand"},
            {"code": "TG", "dial_code": "+228", "name": "Togo"},
            {"code": "TK", "dial_code": "+690", "name": "Tokelau"},
            {"code": "TO", "dial_code": "+676", "name": "Tonga"},
            {"code": "TT", "dial_code": "+1 868", "name": "Trinidad and Tobago"},
            {"code": "TN", "dial_code": "+216", "name": "Tunisia"},
            {"code": "TR", "dial_code": "+90", "name": "Turkey"},
            {"code": "TM", "dial_code": "+993", "name": "Turkmenistan"},
            {"code": "TC", "dial_code": "+1 649", "name": "Turks and Caicos Islands"},
            {"code": "TV", "dial_code": "+688", "name": "Tuvalu"},
            {"code": "UG", "dial_code": "+256", "name": "Uganda"},
            {"code": "UA", "dial_code": "+380", "name": "Ukraine"},
            {"code": "AE", "dial_code": "+971", "name": "United Arab Emirates"},
            {"code": "GB", "dial_code": "+44", "name": "United Kingdom"},
            {"code": "US", "dial_code": "+1", "name": "United States"},
            {"code": "UY", "dial_code": "+598", "name": "Uruguay"},
            {"code": "UZ", "dial_code": "+998", "name": "Uzbekistan"},
            {"code": "VU", "dial_code": "+678", "name": "Vanuatu"},
            {"code": "WF", "dial_code": "+681", "name": "Wallis and Futuna"},
            {"code": "YE", "dial_code": "+967", "name": "Yemen"},
            {"code": "ZM", "dial_code": "+260", "name": "Zambia"},
            {"code": "ZW", "dial_code": "+263", "name": "Zimbabwe"},
            {"code": "AX", "dial_code": "", "name": "\\u00c5land Islands"},
            {"code": "AQ", "dial_code": "", "name": "Antarctica"},
            {"code": "BO", "dial_code": "+591", "name": "Bolivia, Plurinational State of"},
            {"code": "BN", "dial_code": "+673", "name": "Brunei Darussalam"},
            {"code": "CC", "dial_code": "+61", "name": "Cocos (Keeling) Islands"},
            {"code": "CD", "dial_code": "+243", "name": "Congo, The Democratic Republic of the"},
            {"code": "CI", "dial_code": "+225", "name": "C\\u00f4te d\'Ivoire"},
            {"code": "FK", "dial_code": "+500", "name": "Falkland Islands (Malvinas)"},
            {"code": "GG", "dial_code": "+44", "name": "Guernsey"},
            {"code": "VA", "dial_code": "+379", "name": "Holy See (Vatican City State)"},
            {"code": "HK", "dial_code": "+852", "name": "Hong Kong"},
            {"code": "IR", "dial_code": "+98", "name": "Iran, Islamic Republic of"},
            {"code": "IM", "dial_code": "+44", "name": "Isle of Man"},
            {"code": "JE", "dial_code": "+44", "name": "Jersey"},
            {"code": "KP", "dial_code": "+850", "name": "Korea, Democratic People\'s Republic of"},
            {"code": "KR", "dial_code": "+82", "name": "Korea, Republic of"},
            {"code": "LA", "dial_code": "+856", "name": "Lao People\'s Democratic Republic"},
            {"code": "LY", "dial_code": "+218", "name": "Libyan Arab Jamahiriya"},
            {"code": "MO", "dial_code": "+853", "name": "Macao"},
            {"code": "MK", "dial_code": "+389", "name": "Macedonia"},
            {"code": "FM", "dial_code": "+691", "name": "Micronesia, Federated States of"},
            {"code": "MD", "dial_code": "+373", "name": "Moldova, Republic of"},
            {"code": "MZ", "dial_code": "+258", "name": "Mozambique"},
            {"code": "PS", "dial_code": "+970", "name": "Palestinian Territory, Occupied"},
            {"code": "PN", "dial_code": "+872", "name": "Pitcairn"},
            {"code": "RE", "dial_code": "+262", "name": "R\\u00e9union"},
            {"code": "RU", "dial_code": "+7", "name": "Russia"},
            {"code": "BL", "dial_code": "+590", "name": "Saint Barth\\u00e9lemy"},
            {"code": "SH", "dial_code": "+290", "name": "Saint Helena, Ascension and Tristan Da Cunha"},
            {"code": "KN", "dial_code": "+1 869", "name": "Saint Kitts and Nevis"},
            {"code": "LC", "dial_code": "+1 758", "name": "Saint Lucia"},
            {"code": "MF", "dial_code": "+590", "name": "Saint Martin"},
            {"code": "PM", "dial_code": "+508", "name": "Saint Pierre and Miquelon"},
            {"code": "VC", "dial_code": "+1 784", "name": "Saint Vincent and the Grenadines"},
            {"code": "ST", "dial_code": "+239", "name": "Sao Tome and Principe"},
            {"code": "SO", "dial_code": "+252", "name": "Somalia"},
            {"code": "SJ", "dial_code": "+47", "name": "Svalbard and Jan Mayen"},
            {"code": "SY", "dial_code": "+963", "name": "Syrian Arab Republic"},
            {"code": "TW", "dial_code": "+886", "name": "Taiwan, Province of China"},
            {"code": "TZ", "dial_code": "+255", "name": "Tanzania, United Republic of"},
            {"code": "TL", "dial_code": "+670", "name": "Timor-Leste"},
            {"code": "VE", "dial_code": "+58", "name": "Venezuela, Bolivarian Republic of"},
            {"code": "VN", "dial_code": "+84", "name": "Viet Nam"},
            {"code": "VG", "dial_code": "+1 284", "name": "Virgin Islands, British"},
            {"code": "VI", "dial_code": "+1 340", "name": "Virgin Islands, U.S."}]

    countries_created = 0
    try:
        for country_dict in countries[start:]:
            c, created = Country.objects.get_or_create(code=country_dict['code'], name=country_dict['name'])
            if created:
                c.dial_code = country_dict['dial_code']
                c.save()
                countries_created = countries_created + 1
    except DeadlineExceededError:
        logging.info("deffering after %d countries created" % countries_created)
        deferred.defer(do_init, start + countries_created)

    return countries_created



