"""reCAPTCHA v2."""

from json import loads
from urllib.parse import urlencode
from urllib.request import urlopen

RECAPTCHA_RESPONSE_PARAM = 'g-recaptcha-response'
SITE_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'

def verify_recaptcha(response, site_secret):
    """Verifies the the submitted reCAPTCHA response."""
    data = urlencode({'secret': site_secret, 'response': response}, True).encode('utf-8')
    resp = urlopen(SITE_VERIFY_URL, data).read()
    return loads(resp).get('success')
