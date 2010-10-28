import urllib_adaptor


def post(url, data):
    if isinstance(data, dict):
        data = urllib_adaptor.urlencode(data)
    return urllib_adaptor.urlopen(url, data)


def get(url):
    return urllib_adaptor.urlopen(url)