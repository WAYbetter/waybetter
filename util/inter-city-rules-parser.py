# -*- coding: utf-8 -*-
import codecs
import re
in_file = codecs.open('/home/amir/dev/data/inter-city-rules-raw.22-03.11.txt', 'r', "utf-8")
out_file = codecs.open('/home/amir/dev/data/inter-city-rules.csv.utf.22-03.11.txt', 'w', "utf-8")

tlv = re.compile(u"תל אביב")
def clean_city(city):
    if tlv.search(city):
        return u"תל אביב יפו"
    return city

while True:
    from_city = clean_city(in_file.readline().strip())
    if from_city == '':
        break #EOF reached
    to_city = clean_city(in_file.readline().strip())
    tariff1 = in_file.readline().strip()
    tariff2 = in_file.readline().strip()

    s = ','.join( (from_city,to_city,tariff1,tariff2) ) + '\n'
    out_file.write(s)

in_file.close()
out_file.close()

