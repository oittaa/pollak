"""
Cross Site Request Forgery prevention.

This module provides functions that implement protection
against request forgeries from other sites. Based on Django's
standard crypto functions and utilities.
"""
import hashlib
import hmac
import secrets
import warnings

from secrets import compare_digest, token_hex
from time import time

CSRF_TOKEN_TIMEOUT = 3600

class InvalidAlgorithm(ValueError):
    """Algorithm is not supported by hashlib."""


def salted_hmac(key_salt, value, secret, algorithm='sha3_384'):
    """
    Return the HMAC of 'value', using a key generated from key_salt and a
    secret. Default algorithm is SHA3, but any algorithm name supported by
    hashlib.new() can be passed. A different key_salt should be passed in
    for every application of HMAC.
    """
    key_salt = force_bytes(key_salt)
    secret = force_bytes(secret)
    try:
        hasher = getattr(hashlib, algorithm)
    except AttributeError as err:
        raise InvalidAlgorithm(
            '%r is not an algorithm accepted by the hashlib module.'
            % algorithm
        ) from err
    # We need to generate a derived key from our base key.  We can do this by
    # passing the key_salt and our base key through a pseudo-random function.
    key = hasher(key_salt + secret).digest()
    # If len(key_salt + secret) > block size of the hash algorithm, the above
    # line is redundant and could be replaced by key = key_salt + secret, since
    # the hmac module does the same thing for keys longer than the block size.
    # However, we need to ensure that we *always* do this.
    return hmac.new(key, msg=force_bytes(value), digestmod=hasher)


def force_bytes(value, encoding='utf-8', errors='strict'):
    """Return a bytestring version of 'value', encoded as specified in 'encoding'."""
    # Handle the common case first for performance reasons.
    if isinstance(value, bytes):
        if encoding == 'utf-8':
            return value
        return value.decode('utf-8', errors).encode(encoding, errors)
    if isinstance(value, memoryview):
        return bytes(value)
    return str(value).encode(encoding, errors)


def base36_to_int(value):
    """
    Convert a base 36 string to an int. Raise ValueError if the input won't fit
    into an int.
    """
    # To prevent overconsumption of server resources, reject any
    # base36 string that is longer than 13 base36 digits (13 digits
    # is sufficient to base36-encode any 64-bit integer)
    if len(value) > 13:
        raise ValueError("Base36 input too large")
    return int(value, 36)


def int_to_base36(i):
    """Convert an integer to a base36 string."""
    char_set = '0123456789abcdefghijklmnopqrstuvwxyz'
    if i < 0:
        raise ValueError("Negative base36 conversion input.")
    if i < 36:
        return char_set[i]
    b36 = ''
    while i != 0:
        i, remainder = divmod(i, 36)
        b36 = char_set[remainder] + b36
    return b36


def make_csrf_token(value, secret, key_salt=None, timestamp=None):
    """
    Return a CSRF token that can be used to verify that 'value' was
    not modified.
    """
    if key_salt is None:
        key_salt = token_hex(8)
    if timestamp is None:
        timestamp = int(time())
    ts_b36 = int_to_base36(timestamp)
    hash_string = salted_hmac(
        key_salt,
        str(value + ts_b36),
        secret
    ).hexdigest()
    return "%s-%s-%s" % (ts_b36, key_salt, hash_string)


def check_csrf_token(value, secret, token, timeout=CSRF_TOKEN_TIMEOUT):
    """Check that a CSRF token is correct for a given 'value'."""
    if not (value and secret and token):
        return False
    # Parse the token
    try:
        ts_b36, key_salt, _ = token.split("-")
    except ValueError:
        return False

    try:
        ts_int = base36_to_int(ts_b36)
    except ValueError:
        return False

    # Check the timestamp is within limit.
    if (time() - ts_int) > timeout:
        return False

    # Check that the request has not been tampered with.
    if not compare_digest(make_csrf_token(value, secret, key_salt, ts_int), token):
        return False

    return True
