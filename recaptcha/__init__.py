from json import loads
from urllib.parse import urlencode
from urllib.request import urlopen

RECAPTCHA_RESPONSE_PARAM = 'g-recaptcha-response'
SITE_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'

def verify_recaptcha(response, site_secret):
    data = urlencode({'secret': site_secret, 'response': response}, True).encode('utf-8')
    r = urlopen(SITE_VERIFY_URL, data).read()
    return loads(r).get('success')