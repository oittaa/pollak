"""Pollak - Grant Temporary Access to Your Tesla."""
from os import getenv
from re import sub
from time import time
from uuid import uuid4

from flask import Flask, abort, jsonify, make_response, render_template, request
from flask.logging import create_logger
from csrf import check_csrf_token, make_csrf_token
from secretmanager import access_secret_version
from tesla_api import (TeslaApiClient, AuthenticationError, ApiError,
                       OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET)

TITLE = getenv('TITLE', 'Pollak')
HOME_URL = getenv('HOME_URL', 'https://pollak.app')

MAX_ACCESS_DURATION = int(getenv('MAX_ACCESS_DURATION', '240'))
INDEX_CACHE_CONTROL = getenv('INDEX_CACHE_CONTROL', 'public, max-age=600')
RECAPTCHA_SITE_KEY = getenv('RECAPTCHA_SITE_KEY', None)
PROJECT_ID = getenv('PROJECT_ID', getenv('GOOGLE_CLOUD_PROJECT', None))
SECRET_KEY = getenv('SECRET_KEY', None)
SKIP_DATABASE_CONNECTION = getenv('SKIP_DATABASE_CONNECTION', None)
SEND_FILE_MAX_AGE_DEFAULT = int(getenv('SEND_FILE_MAX_AGE_DEFAULT', '2592000'))

# Enable GCP Logging if inside an App Engine instance
if getenv('GAE_APPLICATION', None):
    # Imports the Google Cloud client library
    import google.cloud.logging

    # Instantiates a client
    GCP_LOG_CLIENT = google.cloud.logging.Client()

    # Connects the logger to the root logging handler; by default this captures
    # all logs at INFO level and higher
    GCP_LOG_CLIENT.setup_logging()

# If env variable SECRET_KEY is not defined, fetch it from Secret Manager
if SECRET_KEY is None:
    SECRET_KEY_ID = getenv('SECRET_KEY_ID', 'GAE_SECRET_KEY')
    SECRET_KEY = access_secret_version(PROJECT_ID, SECRET_KEY_ID)

# If env variable RECAPTCHA_SITE_SECRET is not defined, fetch it from Secret Manager
if RECAPTCHA_SITE_KEY:
    from recaptcha import verify_recaptcha, RECAPTCHA_RESPONSE_PARAM
    RECAPTCHA_SITE_SECRET = getenv('RECAPTCHA_SITE_SECRET', None)
    if RECAPTCHA_SITE_SECRET is None:
        RECAPTCHA_SECRET_ID = getenv('RECAPTCHA_SECRET_ID', 'RECAPTCHA_SITE_SECRET')
        RECAPTCHA_SITE_SECRET = access_secret_version(PROJECT_ID, RECAPTCHA_SECRET_ID)



# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)  # pylint: disable=invalid-name
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = SEND_FILE_MAX_AGE_DEFAULT
LOG = create_logger(app)

# database abstraction
if SKIP_DATABASE_CONNECTION:
    from database import MemoryDatabase
    db = MemoryDatabase()  # pylint: disable=invalid-name
else:
    from database import Firestore
    db = Firestore()  # pylint: disable=invalid-name

@app.route('/', methods=['GET'])
def index():
    """Main page."""
    response = make_response(render_template(
        "index.html", title=TITLE, home_url=HOME_URL, oauth_client_id=OAUTH_CLIENT_ID,
        oauth_client_secret=OAUTH_CLIENT_SECRET, recaptcha_site_key=RECAPTCHA_SITE_KEY))
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = INDEX_CACHE_CONTROL
        response.add_etag()
    return response

@app.route('/login', methods=['POST'])
def login():
    """After login, choose vehicle and access duration."""
    email = password = token = error_msg = csrf = None

    if request.form['token']:
        token = _get_token(refresh_token=request.form['token'])
    elif request.form['email'] and request.form['password']:
        email = request.form['email']
        password = request.form['password']
    else:
        abort(400)

    if RECAPTCHA_SITE_KEY:
        try:
            response = request.form[RECAPTCHA_RESPONSE_PARAM]
        except ValueError:
            abort(400)
        if verify_recaptcha(response, RECAPTCHA_SITE_SECRET):
            LOG.info('reCAPTCHA success')
        else:
            LOG.warning('reCAPTCHA failure')
            error_msg = 'reCAPTCHA failure'

    client = TeslaApiClient(email, password, token)
    vehicles = token = None
    if error_msg is None:
        try:
            vehicles = client.list_vehicles()
            token = client.token['refresh_token']
            csrf = make_csrf_token(token, SECRET_KEY)
        except AuthenticationError:
            error_msg = 'Authentication failure'

    return render_template("login.html", title=TITLE, vehicles=vehicles, token=token,
                           csrf=csrf, max_access_duration=MAX_ACCESS_DURATION, error_msg=error_msg)

@app.route('/authorize', methods=['POST'])
def authorize():
    """Authorize access and show the URL for user page."""
    if not check_csrf_token(request.form['token'], SECRET_KEY, request.form['csrf']):
        LOG.warning('CSRF failed')
        abort(403)
    try:
        vehicle_id = request.form['vehicle']
        begins_at = int(request.form['begins_at'])
        expires_at = int(request.form['expires_at'])
        assert vehicle_id.isnumeric()
        assert 0 <= begins_at <= MAX_ACCESS_DURATION - 1
        assert 1 <= expires_at <= MAX_ACCESS_DURATION
        assert begins_at < expires_at
    except (ValueError, AssertionError) as _error_msg:
        abort(400)
    token = _get_token(refresh_token=request.form['token'])
    client = TeslaApiClient(token=token)
    try:
        # Make sure the token and vehicle_id are valid
        _data = client.get_vehicle(vehicle_id)
    except AuthenticationError:
        abort(403)
    user_id = str(uuid4())
    # Convert submitted times to Unix timestamps
    now = int(time())
    begins_at = now + begins_at * 3600
    expires_at = now + expires_at * 3600
    data = {
        "token": client.token,
        "vehicle_id": vehicle_id,
        "begins_at": begins_at,
        "expires_at": expires_at
        }
    db.add_user(user_id, data)
    return render_template("authorize.html", title=TITLE, user_id=user_id)

@app.route('/user/<uuid:user_id>', methods=['GET'])
def user_page(user_id):
    """Show the vehicle data associated with the user."""
    user_id = str(user_id)
    now = int(time())
    user_data = db.get_user(user_id)
    if not user_data:
        abort(404)
    if now < user_data['begins_at']:
        return render_template("user_wait.html", title=TITLE, begins_at=user_data['begins_at'])
    if now > user_data['expires_at']:
        db.delete_user(user_id)
        abort(404)
    client = TeslaApiClient(token=user_data['token'])
    try:
        # Make sure the token and vehicle_id are valid
        vehicle = client.get_vehicle(user_data['vehicle_id'])
    except AuthenticationError:
        abort(403)

    # Return template immediately and fill the rest with JSON-requests.
    if not request.args.get('json'):
        return render_template("user_page.html", title=TITLE, user_id=user_id,
                               vehicle_name=vehicle.display_name)

    api_error = False
    response = {}
    try:
        if vehicle.state != "online":
            _resp = vehicle.wake_up()
        data = vehicle.get_data()
        response['battery_level'] = data['charge_state'].get('battery_level')
        response['charging_state'] = data['charge_state'].get('charging_state')
        response['is_climate_on'] = data['climate_state'].get('is_climate_on')
        response['temp_setting'] = data['climate_state'].get('driver_temp_setting')
        response['inside_temp'] = data['climate_state'].get('inside_temp')
        response['outside_temp'] = data['climate_state'].get('outside_temp')
        response['gui_temperature_units'] = data['gui_settings'].get('gui_temperature_units')
        response['locked'] = data['vehicle_state'].get('locked')
        response['vehicle_name'] = vehicle.display_name
    except ApiError as error_msg:
        api_error = True
        LOG.info("Remote API error: %s", error_msg)

    return jsonify(response=response, api_error=api_error)

@app.route('/api', methods=['POST'])
def api():
    """API to control the vehicle."""
    commands = ['start_climate', 'stop_climate']
    now = int(time())

    try:
        user_id = request.form['user_id']
        command = request.form['command']
    except ValueError:
        abort(400)

    if not command in commands:
        abort(400)

    user_data = db.get_user(user_id)
    if not user_data:
        abort(403)
    if now < user_data['begins_at']:
        abort(403)
    if now > user_data['expires_at']:
        db.delete_user(user_id)
        abort(403)

    client = TeslaApiClient(token=user_data['token'])
    try:
        # Make sure the token and vehicle_id are valid
        vehicle = client.get_vehicle(user_data['vehicle_id'])
    except AuthenticationError:
        abort(403)

    try:
        if command == 'start_climate':
            data = vehicle.climate.start_climate()
        if command == 'stop_climate':
            data = vehicle.climate.stop_climate()
    except ApiError as error_msg:
        data = {'result': False}
        LOG.info("Remote API error: %s", error_msg)
    return jsonify(data)

@app.route('/cron', methods=['GET'])
def cron():
    """Cron function that cleans expired users from the database."""
    if request.headers.get('X-Appengine-Cron') is None:
        abort(403)
    db.cleanup()
    return 'Success!'


def _get_token(access_token="", refresh_token="", expires_in=0, created_at=0):
    return {
        "access_token": _filter_input(access_token),
        "refresh_token": _filter_input(refresh_token),
        "expires_in": expires_in,
        "created_at": created_at
        }

def _filter_input(string):
    return sub('[^A-Za-z0-9]', '', string)

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
