in_file = open('../data/inter-city-rules-raw.txt', 'r')
out_file = open('../data/inter-city-rules.csv.utf.txt', 'w')


def clean_rtl(str):
    return str.decode("utf-8").replace(u"\u202b","").replace(u"\u202c","")

while True:
    tariff2 = clean_rtl(in_file.readline().strip())
    if tariff2 == '':
        break #EOF reached
    tariff1 = clean_rtl(in_file.readline().strip())
    to_city = clean_rtl(in_file.readline().strip())
    from_city = clean_rtl(in_file.readline().strip())

    s = ','.join( (from_city,to_city,tariff1,tariff2) ) + '\n'
    out_file.write(s.encode("utf-8"))

in_file.close()
out_file.close()

