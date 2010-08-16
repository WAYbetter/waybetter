# Create your views here.
from django.contrib.auth.models import User
from django.http import HttpResponse
from ordering.models import Order, WorkStation
from google.appengine.api import xmpp
import logging
from django.contrib.auth.decorators import login_required
from common.models import Country, Country

def setup(request):
    if "token" in request.GET:
        if request.GET["token"] == 'waybetter_init':
            if User.objects.filter(username = "waybetter_admin").count() == 0:
                u = User()
                u.username = "waybetter_admin"
                u.set_password('waybetter_admin')
                u.email = "guykrem@gmail.com"
                u.is_active = True
                u.is_staff = True
                u.is_superuser = True
                u.save()
                return HttpResponse('Admin created!')

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

def init_countries(request):
    if Country.objects.all().count() > 1:
        from django.core.serializers import serialize
        cc = Country.objects.all()
        return HttpResponse(serialize("json", cc))

    countries = [{"dial_code": "+93", "code": "AF", "name": "Afghanistan"}, {"code": "AX", "name": "\u00c5land Islands"}
                 , {"dial_code": "+355", "code": "AL", "name": "Albania"},
                 {"dial_code": "+213", "code": "DZ", "name": "Algeria"},
                 {"dial_code": "+1 684", "code": "AS", "name": "American Samoa"},
                 {"dial_code": "+376", "code": "AD", "name": "Andorra"},
                 {"dial_code": "+244", "code": "AO", "name": "Angola"},
                 {"dial_code": "+1 264", "code": "AI", "name": "Anguilla"}, {"code": "AQ", "name": "Antarctica"},
                 {"dial_code": "+1 268", "code": "AG", "name": "Antigua and Barbuda"},
                 {"dial_code": "+54", "code": "AR", "name": "Argentina"},
                 {"dial_code": "+374", "code": "AM", "name": "Armenia"},
                 {"dial_code": "+297", "code": "AW", "name": "Aruba"},
                 {"dial_code": "+61", "code": "AU", "name": "Australia"},
                 {"dial_code": "+43", "code": "AT", "name": "Austria"},
                 {"dial_code": "+994", "code": "AZ", "name": "Azerbaijan"},
                 {"dial_code": "+1 242", "code": "BS", "name": "Bahamas"},
                 {"dial_code": "+973", "code": "BH", "name": "Bahrain"},
                 {"dial_code": "+880", "code": "BD", "name": "Bangladesh"},
                 {"dial_code": "+1 246", "code": "BB", "name": "Barbados"},
                 {"dial_code": "+375", "code": "BY", "name": "Belarus"},
                 {"dial_code": "+32", "code": "BE", "name": "Belgium"},
                 {"dial_code": "+501", "code": "BZ", "name": "Belize"},
                 {"dial_code": "+229", "code": "BJ", "name": "Benin"},
                 {"dial_code": "+1 441", "code": "BM", "name": "Bermuda"},
                 {"dial_code": "+975", "code": "BT", "name": "Bhutan"},
                 {"code": "BO", "name": "Bolivia, Plurinational State of"},
                 {"dial_code": "+387", "code": "BA", "name": "Bosnia and Herzegovina"},
                 {"dial_code": "+267", "code": "BW", "name": "Botswana"}, {"code": "BV", "name": "Bouvet Island"},
                 {"dial_code": "+55", "code": "BR", "name": "Brazil"},
                 {"dial_code": "+246", "code": "IO", "name": "British Indian Ocean Territory"},
                 {"code": "BN", "name": "Brunei Darussalam"}, {"dial_code": "+359", "code": "BG", "name": "Bulgaria"},
                 {"dial_code": "+226", "code": "BF", "name": "Burkina Faso"},
                 {"dial_code": "+257", "code": "BI", "name": "Burundi"},
                 {"dial_code": "+855", "code": "KH", "name": "Cambodia"},
                 {"dial_code": "+237", "code": "CM", "name": "Cameroon"},
                 {"dial_code": "+1", "code": "CA", "name": "Canada"},
                 {"dial_code": "+238", "code": "CV", "name": "Cape Verde"},
                 {"dial_code": "+ 345", "code": "KY", "name": "Cayman Islands"},
                 {"dial_code": "+236", "code": "CF", "name": "Central African Republic"},
                 {"dial_code": "+235", "code": "TD", "name": "Chad"},
                 {"dial_code": "+56", "code": "CL", "name": "Chile"},
                 {"dial_code": "+86", "code": "CN", "name": "China"},
                 {"dial_code": "+61", "code": "CX", "name": "Christmas Island"},
                 {"code": "CC", "name": "Cocos (Keeling) Islands"},
                 {"dial_code": "+57", "code": "CO", "name": "Colombia"},
                 {"dial_code": "+269", "code": "KM", "name": "Comoros"},
                 {"dial_code": "+242", "code": "CG", "name": "Congo"},
                 {"code": "CD", "name": "Congo, The Democratic Republic of the"},
                 {"dial_code": "+682", "code": "CK", "name": "Cook Islands"},
                 {"dial_code": "+506", "code": "CR", "name": "Costa Rica"}, {"code": "CI", "name": "C\u00f4te d'Ivoire"}
                 , {"dial_code": "+385", "code": "HR", "name": "Croatia"},
                 {"dial_code": "+53", "code": "CU", "name": "Cuba"},
                 {"dial_code": "+537", "code": "CY", "name": "Cyprus"},
                 {"dial_code": "+420", "code": "CZ", "name": "Czech Republic"},
                 {"dial_code": "+45", "code": "DK", "name": "Denmark"},
                 {"dial_code": "+253", "code": "DJ", "name": "Djibouti"},
                 {"dial_code": "+1 767", "code": "DM", "name": "Dominica"},
                 {"dial_code": "+1 849", "code": "DO", "name": "Dominican Republic"},
                 {"dial_code": "+593", "code": "EC", "name": "Ecuador"},
                 {"dial_code": "+20", "code": "EG", "name": "Egypt"},
                 {"dial_code": "+503", "code": "SV", "name": "El Salvador"},
                 {"dial_code": "+240", "code": "GQ", "name": "Equatorial Guinea"},
                 {"dial_code": "+291", "code": "ER", "name": "Eritrea"},
                 {"dial_code": "+372", "code": "EE", "name": "Estonia"},
                 {"dial_code": "+251", "code": "ET", "name": "Ethiopia"},
                 {"code": "FK", "name": "Falkland Islands (Malvinas)"},
                 {"dial_code": "+298", "code": "FO", "name": "Faroe Islands"},
                 {"dial_code": "+679", "code": "FJ", "name": "Fiji"},
                 {"dial_code": "+358", "code": "FI", "name": "Finland"},
                 {"dial_code": "+33", "code": "FR", "name": "France"},
                 {"dial_code": "+594", "code": "GF", "name": "French Guiana"},
                 {"dial_code": "+689", "code": "PF", "name": "French Polynesia"},
                 {"code": "TF", "name": "French Southern Territories"},
                 {"dial_code": "+241", "code": "GA", "name": "Gabon"},
                 {"dial_code": "+220", "code": "GM", "name": "Gambia"},
                 {"dial_code": "+995", "code": "GE", "name": "Georgia"},
                 {"dial_code": "+49", "code": "DE", "name": "Germany"},
                 {"dial_code": "+233", "code": "GH", "name": "Ghana"},
                 {"dial_code": "+350", "code": "GI", "name": "Gibraltar"},
                 {"dial_code": "+30", "code": "GR", "name": "Greece"},
                 {"dial_code": "+299", "code": "GL", "name": "Greenland"},
                 {"dial_code": "+1 473", "code": "GD", "name": "Grenada"},
                 {"dial_code": "+590", "code": "GP", "name": "Guadeloupe"},
                 {"dial_code": "+1 671", "code": "GU", "name": "Guam"},
                 {"dial_code": "+502", "code": "GT", "name": "Guatemala"}, {"code": "GG", "name": "Guernsey"},
                 {"dial_code": "+224", "code": "GN", "name": "Guinea"},
                 {"dial_code": "+245", "code": "GW", "name": "Guinea-Bissau"},
                 {"dial_code": "+595", "code": "GY", "name": "Guyana"},
                 {"dial_code": "+509", "code": "HT", "name": "Haiti"},
                 {"code": "HM", "name": "Heard Island and McDonald Islands"},
                 {"code": "VA", "name": "Holy See (Vatican City State)"},
                 {"dial_code": "+504", "code": "HN", "name": "Honduras"}, {"code": "HK", "name": "Hong Kong"},
                 {"dial_code": "+36", "code": "HU", "name": "Hungary"},
                 {"dial_code": "+354", "code": "IS", "name": "Iceland"},
                 {"dial_code": "+91", "code": "IN", "name": "India"},
                 {"dial_code": "+62", "code": "ID", "name": "Indonesia"},
                 {"code": "IR", "name": "Iran, Islamic Republic of"},
                 {"dial_code": "+964", "code": "IQ", "name": "Iraq"},
                 {"dial_code": "+353", "code": "IE", "name": "Ireland"}, {"code": "IM", "name": "Isle of Man"},
                 {"dial_code": "+972", "code": "IL", "name": "Israel"},
                 {"dial_code": "+39", "code": "IT", "name": "Italy"},
                 {"dial_code": "+1 876", "code": "JM", "name": "Jamaica"},
                 {"dial_code": "+81", "code": "JP", "name": "Japan"}, {"code": "JE", "name": "Jersey"},
                 {"dial_code": "+962", "code": "JO", "name": "Jordan"},
                 {"dial_code": "+7 7", "code": "KZ", "name": "Kazakhstan"},
                 {"dial_code": "+254", "code": "KE", "name": "Kenya"},
                 {"dial_code": "+686", "code": "KI", "name": "Kiribati"},
                 {"code": "KP", "name": "Korea, Democratic People's Republic of"},
                 {"code": "KR", "name": "Korea, Republic of"}, {"dial_code": "+965", "code": "KW", "name": "Kuwait"},
                 {"dial_code": "+996", "code": "KG", "name": "Kyrgyzstan"},
                 {"code": "LA", "name": "Lao People's Democratic Republic"},
                 {"dial_code": "+371", "code": "LV", "name": "Latvia"},
                 {"dial_code": "+961", "code": "LB", "name": "Lebanon"},
                 {"dial_code": "+266", "code": "LS", "name": "Lesotho"},
                 {"dial_code": "+231", "code": "LR", "name": "Liberia"},
                 {"code": "LY", "name": "Libyan Arab Jamahiriya"},
                 {"dial_code": "+423", "code": "LI", "name": "Liechtenstein"},
                 {"dial_code": "+370", "code": "LT", "name": "Lithuania"},
                 {"dial_code": "+352", "code": "LU", "name": "Luxembourg"}, {"code": "MO", "name": "Macao"},
                 {"code": "MK", "name": "Macedonia, The Former Yugoslav Republic of"},
                 {"dial_code": "+261", "code": "MG", "name": "Madagascar"},
                 {"dial_code": "+265", "code": "MW", "name": "Malawi"},
                 {"dial_code": "+60", "code": "MY", "name": "Malaysia"},
                 {"dial_code": "+960", "code": "MV", "name": "Maldives"},
                 {"dial_code": "+223", "code": "ML", "name": "Mali"},
                 {"dial_code": "+356", "code": "MT", "name": "Malta"},
                 {"dial_code": "+692", "code": "MH", "name": "Marshall Islands"},
                 {"dial_code": "+596", "code": "MQ", "name": "Martinique"},
                 {"dial_code": "+222", "code": "MR", "name": "Mauritania"},
                 {"dial_code": "+230", "code": "MU", "name": "Mauritius"},
                 {"dial_code": "+262", "code": "YT", "name": "Mayotte"},
                 {"dial_code": "+52", "code": "MX", "name": "Mexico"},
                 {"code": "FM", "name": "Micronesia, Federated States of"},
                 {"code": "MD", "name": "Moldova, Republic of"}, {"dial_code": "+377", "code": "MC", "name": "Monaco"},
                 {"dial_code": "+976", "code": "MN", "name": "Mongolia"},
                 {"dial_code": "+382", "code": "ME", "name": "Montenegro"},
                 {"dial_code": "+1664", "code": "MS", "name": "Montserrat"},
                 {"dial_code": "+212", "code": "MA", "name": "Morocco"}, {"code": "MZ", "name": "Mozambique"},
                 {"dial_code": "+95", "code": "MM", "name": "Myanmar"},
                 {"dial_code": "+264", "code": "NA", "name": "Namibia"},
                 {"dial_code": "+674", "code": "NR", "name": "Nauru"},
                 {"dial_code": "+977", "code": "NP", "name": "Nepal"},
                 {"dial_code": "+31", "code": "NL", "name": "Netherlands"},
                 {"dial_code": "+599", "code": "AN", "name": "Netherlands Antilles"},
                 {"dial_code": "+687", "code": "NC", "name": "New Caledonia"},
                 {"dial_code": "64", "code": "NZ", "name": "New Zealand"},
                 {"dial_code": "+505", "code": "NI", "name": "Nicaragua"},
                 {"dial_code": "+227", "code": "NE", "name": "Niger"},
                 {"dial_code": "+234", "code": "NG", "name": "Nigeria"},
                 {"dial_code": "+683", "code": "NU", "name": "Niue"},
                 {"dial_code": "+672", "code": "NF", "name": "Norfolk Island"},
                 {"dial_code": "+1 670", "code": "MP", "name": "Northern Mariana Islands"},
                 {"dial_code": "+47", "code": "NO", "name": "Norway"},
                 {"dial_code": "+968", "code": "OM", "name": "Oman"},
                 {"dial_code": "+92", "code": "PK", "name": "Pakistan"},
                 {"dial_code": "+680", "code": "PW", "name": "Palau"},
                 {"code": "PS", "name": "Palestinian Territory, Occupied"},
                 {"dial_code": "+507", "code": "PA", "name": "Panama"},
                 {"dial_code": "+675", "code": "PG", "name": "Papua New Guinea"},
                 {"dial_code": "+595", "code": "PY", "name": "Paraguay"},
                 {"dial_code": "+51", "code": "PE", "name": "Peru"},
                 {"dial_code": "+63", "code": "PH", "name": "Philippines"}, {"code": "PN", "name": "Pitcairn"},
                 {"dial_code": "+48", "code": "PL", "name": "Poland"},
                 {"dial_code": "+351", "code": "PT", "name": "Portugal"},
                 {"dial_code": "+1 939", "code": "PR", "name": "Puerto Rico"},
                 {"dial_code": "+974", "code": "QA", "name": "Qatar"}, {"code": "RE", "name": "R\u00e9union"},
                 {"dial_code": "+40", "code": "RO", "name": "Romania"}, {"code": "RU", "name": "Russian Federation"},
                 {"dial_code": "+250", "code": "RW", "name": "Rwanda"}, {"code": "BL", "name": "Saint Barth\u00e9lemy"},
                 {"code": "SH", "name": "Saint Helena, Ascension and Tristan Da Cunha"},
                 {"code": "KN", "name": "Saint Kitts and Nevis"}, {"code": "LC", "name": "Saint Lucia"},
                 {"code": "MF", "name": "Saint Martin"}, {"code": "PM", "name": "Saint Pierre and Miquelon"},
                 {"code": "VC", "name": "Saint Vincent and the Grenadines"},
                 {"dial_code": "+685", "code": "WS", "name": "Samoa"},
                 {"dial_code": "+378", "code": "SM", "name": "San Marino"},
                 {"code": "ST", "name": "Sao Tome and Principe"},
                 {"dial_code": "+966", "code": "SA", "name": "Saudi Arabia"},
                 {"dial_code": "+221", "code": "SN", "name": "Senegal"},
                 {"dial_code": "+381", "code": "RS", "name": "Serbia"},
                 {"dial_code": "+248", "code": "SC", "name": "Seychelles"},
                 {"dial_code": "+232", "code": "SL", "name": "Sierra Leone"},
                 {"dial_code": "+65", "code": "SG", "name": "Singapore"},
                 {"dial_code": "+421", "code": "SK", "name": "Slovakia"},
                 {"dial_code": "+386", "code": "SI", "name": "Slovenia"},
                 {"dial_code": "+677", "code": "SB", "name": "Solomon Islands"}, {"code": "SO", "name": "Somalia"},
                 {"dial_code": "+27", "code": "ZA", "name": "South Africa"},
                 {"dial_code": "+500", "code": "GS", "name": "South Georgia and the South Sandwich Islands"},
                 {"dial_code": "+34", "code": "ES", "name": "Spain"},
                 {"dial_code": "+94", "code": "LK", "name": "Sri Lanka"},
                 {"dial_code": "+249", "code": "SD", "name": "Sudan"},
                 {"dial_code": "+597", "code": "SR", "name": "Suriname"},
                 {"code": "SJ", "name": "Svalbard and Jan Mayen"},
                 {"dial_code": "+268", "code": "SZ", "name": "Swaziland"},
                 {"dial_code": "+46", "code": "SE", "name": "Sweden"},
                 {"dial_code": "+41", "code": "CH", "name": "Switzerland"},
                 {"code": "SY", "name": "Syrian Arab Republic"}, {"code": "TW", "name": "Taiwan, Province of China"},
                 {"dial_code": "+992", "code": "TJ", "name": "Tajikistan"},
                 {"code": "TZ", "name": "Tanzania, United Republic of"},
                 {"dial_code": "+66", "code": "TH", "name": "Thailand"}, {"code": "TL", "name": "Timor-Leste"},
                 {"dial_code": "+228", "code": "TG", "name": "Togo"},
                 {"dial_code": "+690", "code": "TK", "name": "Tokelau"},
                 {"dial_code": "+676", "code": "TO", "name": "Tonga"},
                 {"dial_code": "+1 868", "code": "TT", "name": "Trinidad and Tobago"},
                 {"dial_code": "+216", "code": "TN", "name": "Tunisia"},
                 {"dial_code": "+90", "code": "TR", "name": "Turkey"},
                 {"dial_code": "+993", "code": "TM", "name": "Turkmenistan"},
                 {"dial_code": "+1 649", "code": "TC", "name": "Turks and Caicos Islands"},
                 {"dial_code": "+688", "code": "TV", "name": "Tuvalu"},
                 {"dial_code": "+256", "code": "UG", "name": "Uganda"},
                 {"dial_code": "+380", "code": "UA", "name": "Ukraine"},
                 {"dial_code": "+971", "code": "AE", "name": "United Arab Emirates"},
                 {"dial_code": "+44", "code": "GB", "name": "United Kingdom"},
                 {"dial_code": "+1", "code": "US", "name": "United States"},
                 {"code": "UM", "name": "United States Minor Outlying Islands"},
                 {"dial_code": "+598", "code": "UY", "name": "Uruguay"},
                 {"dial_code": "+998", "code": "UZ", "name": "Uzbekistan"},
                 {"dial_code": "+678", "code": "VU", "name": "Vanuatu"},
                 {"code": "VE", "name": "Venezuela, Bolivarian Republic of"}, {"code": "VN", "name": "Viet Nam"},
                 {"code": "VG", "name": "Virgin Islands, British"}, {"code": "VI", "name": "Virgin Islands, U.S."},
                 {"dial_code": "+681", "code": "WF", "name": "Wallis and Futuna"},
                 {"code": "EH", "name": "Western Sahara"}, {"dial_code": "+967", "code": "YE", "name": "Yemen"},
                 {"dial_code": "+260", "code": "ZM", "name": "Zambia"},
                 {"dial_code": "+263", "code": "ZW", "name": "Zimbabwe"}]

    countries_created = 0
    for country_dict in countries:
        if "dial_code" not in country_dict:
            c = Country()
            c.name = country_dict['name']
#            c.dial_code = country_dict['dial_code']
            c.code = country_dict['code']
            c.save()
            countries_created = countries_created +1


    return HttpResponse("%d countries created" % countries_created)


