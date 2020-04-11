"""Tesla API."""

from datetime import datetime, timedelta
import requests
from .vehicle import Vehicle

TESLA_API_BASE_URL = 'https://owner-api.teslamotors.com/'
TOKEN_URL = TESLA_API_BASE_URL + 'oauth/token'
API_URL = TESLA_API_BASE_URL + 'api/1'

OAUTH_CLIENT_ID = '81527cff06843c8634fdc09e8ac0abefb46ac849f38fe1e431c2ef2106796384'
OAUTH_CLIENT_SECRET = 'c7257eb71a564034f9419ee651c7d0e5f7aa6bfbd18bafb5c5c033b093bb2fa3'

class TeslaApiClient:
    """Client for Tesla API."""
    def __init__(self, email=None, password=None, token=None):
        """Creates client from provided credentials.

        If token is not provided, or is no longer valid, then a new token will
        be fetched if email and password are provided.
        """
        assert token is not None or (email is not None and password is not None)
        self._email = email
        self._password = password
        self.token = token

    def _get_new_token(self):
        request_data = {
            'grant_type': 'password',
            'client_id': OAUTH_CLIENT_ID,
            'client_secret': OAUTH_CLIENT_SECRET,
            'email': self._email,
            'password': self._password
        }

        resp = requests.post(TOKEN_URL, data=request_data)
        response_json = resp.json()
        if resp.status_code == 401:
            raise AuthenticationError(response_json)

        return response_json

    def _refresh_token(self):
        request_data = {
            'grant_type': 'refresh_token',
            'client_id': OAUTH_CLIENT_ID,
            'client_secret': OAUTH_CLIENT_SECRET,
            'refresh_token': self.token['refresh_token'],
        }

        resp = requests.post(TOKEN_URL, data=request_data)
        response_json = resp.json()
        if resp.status_code == 401:
            raise AuthenticationError(response_json)

        return response_json

    def authenticate(self):
        """Authenticate with access token or try to get new token with refresh token."""
        if not self.token:
            self.token = self._get_new_token()

        expiry_time = timedelta(seconds=self.token['expires_in'])
        expiration_date = datetime.fromtimestamp(self.token['created_at']) + expiry_time

        if datetime.utcnow() >= expiration_date:
            self.token = self._refresh_token()

    def _get_headers(self):
        return {
            'Authorization': 'Bearer {}'.format(self.token['access_token'])
        }

    def get(self, endpoint):
        """GET request against the API endpoint."""
        self.authenticate()
        url = '{}/{}'.format(API_URL, endpoint)

        resp = requests.get(url, headers=self._get_headers())
        response_json = resp.json()

        if 'error' in response_json:
            raise ApiError(response_json['error'])

        return response_json['response']

    def post(self, endpoint, data=None):
        """POST request against the API endpoint."""
        self.authenticate()
        url = '{}/{}'.format(API_URL, endpoint)
        if data is None:
            data = {}

        resp = requests.post(url, headers=self._get_headers(), json=data)
        response_json = resp.json()

        if 'error' in response_json:
            raise ApiError(response_json['error'])

        return response_json['response']

    def get_vehicle(self, vehicle_id, _class=Vehicle):
        """A specific vehicle for the authenticated user."""
        self.authenticate()
        url = '{}/vehicles/{}'.format(API_URL, vehicle_id)

        resp = requests.get(url, headers=self._get_headers())
        if resp.status_code == 401:
            raise AuthenticationError(resp.text)
        response_json = resp.json()

        if 'error' in response_json:
            raise ApiError(response_json['error'])

        return _class(self, response_json['response'])

    def list_vehicles(self, _class=Vehicle):
        """All vehicles for the authenticated user."""
        return [_class(self, vehicle) for vehicle in self.get('vehicles')]

class AuthenticationError(Exception):
    """Authentication error."""
    def __init__(self, error):
        super().__init__('Authentication to the Tesla API failed: {}'.format(error))

class ApiError(Exception):
    """API error."""
    def __init__(self, error):
        super().__init__('Tesla API call failed: {}'.format(error))
