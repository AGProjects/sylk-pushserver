import json
import os
import time

import oauth2client
import requests
from oauth2client.service_account import ServiceAccountCredentials

from pushserver.models.requests import WakeUpRequest

from requests.adapters import HTTPAdapter
from urllib3 import Retry

from pushserver.pns.base import PNS, PushRequest, PlatformRegister
from pushserver.resources.utils import log_event, fix_non_serializable_types


class FirebasePNS(PNS):
    """
    A Firebase Push Notification service
    """

    def __init__(self, app_id: str, app_name: str, url_push: str,
                 voip: bool, auth_key: str = None, auth_file: str = None):
        """
        :param app_id `str`: Application ID.
        :param url_push `str`: URI to push a notification.
        :param voip `bool`:  required for apple, `True` for voip push notification type.
        :param auth_key `str`: A Firebase credential for push notifications.
        :param auth_file `str`: A Firebase credential for push notifications.
        """
        self.app_id = app_id
        self.app_name = app_name
        self.url_push = url_push
        self.voip = voip
        self.auth_key = auth_key
        self.auth_file = auth_file
        self.error = ''
        self.access_token = self.set_access_token()

    def set_access_token(self) -> str:
        """
        Retrieve a valid access token that can be used to authorize requests.
        :return: `str` Access token.
        """

        if not self.auth_file:
            self.error = f"Cannot generated Firebase access token, " \
                         f"no auth file provided"
            return ''

        if not os.path.exists(self.auth_file):
            self.error = f"Cannot generated Firebase access token, " \
                  f"auth file {self.auth_file} not found"
            return ''

        scopes = ['https://www.googleapis.com/auth/firebase.messaging']
        try:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(self.auth_file,
                                                                           scopes)
            oauth2client.client.logger.setLevel('CRITICAL')
            access_token_info = credentials.get_access_token()

            return access_token_info.access_token
        except Exception as e:
            self.error = f"Error: cannot generated Firebase access token: {e}"
            return ''


class FirebaseRegister(PlatformRegister):
    def __init__(self, app_id: str, app_name: str, voip: bool,
                 config_dict: dict, credentials_path: str, loggers: dict):

        self.app_id = app_id
        self.app_name = app_name
        self.voip = voip

        self.credentials_path = credentials_path
        self.config_dict = config_dict
        self.loggers = loggers

        self.error = ''
        self.auth_key, self.auth_file = self.set_auths()

    @property
    def url_push(self):
        try:
            return self.config_dict['firebase_push_url']
        except KeyError:
            self.error = 'firebase_push_url not found in applications.ini'
            return None

    def set_auths(self):

        auth_key = None
        auth_file = None
        try:
            auth_key = self.config_dict['firebase_authorization_key']
        except KeyError:
            try:
                auth_file = self.config_dict['firebase_authorization_file']
                if self.credentials_path:
                    auth_file = f"{self.credentials_path}/" \
                                f"{auth_file}"
                else:
                    pass
                if not os.path.exists(auth_file):
                    self.error = f'{auth_file} - no such file'
            except KeyError:
                self.error = 'not firebase_authorization_key or ' \
                             'firebase_authorization_file found in applications.ini'

        return auth_key, auth_file

    @property
    def pns(self) -> FirebasePNS:
        pns = None
        if self.auth_key:
            auth_file = ''
            pns = FirebasePNS(app_id=self.app_id,
                              app_name=self.app_name,
                              url_push=self.url_push,
                              voip=self.voip,
                              auth_key=self.auth_key,
                              auth_file=auth_file)
        elif self.auth_file:
            pns = FirebasePNS(app_id=self.app_id,
                              app_name=self.app_name,
                              url_push=self.url_push,
                              voip=self.voip,
                              auth_file=self.auth_file)

            self.error = pns.error if pns.error else ''
        return pns

    @property
    def register_entries(self):
        if self.error:
            return {}

        return {'pns': self.pns,
                'access_token': self.pns.access_token,
                'auth_key': self.auth_key,
                'auth_file': self.auth_file,
                'refreshed_token': False}


class FirebasePushRequest(PushRequest):
    """
    Firebase push notification request
    """

    def __init__(self, error: str, app_name: str, app_id: str,
                 request_id: str, headers: str, payload: dict,
                 loggers: dict, log_remote: dict,
                 wp_request: WakeUpRequest, register: dict):

        """
        :param error: `str`
        :param app_name: `str` 'linphone' or 'payload'
        :param app_id: `str` bundle id
        :param headers: `AppleHeaders` Apple push notification headers
        :param payload: `ApplePayload` Apple push notification payload
        :param wp_request: `WakeUpRequest`
        :param loggers: `dict` global logging instances to write messages (params.loggers)
        """
        self.error = error
        self.app_name = app_name
        self.app_id = app_id
        self.platform = 'firebase'
        self.request_id = request_id
        self.headers = headers
        self.payload = payload
        self.token = wp_request.token
        self.wp_request = wp_request
        self.loggers = loggers
        self.log_remote = log_remote

        self.pns = register['pns']
        self.path = self.pns.url_push
        self.results = self.send_notification()

    def requests_retry_session(self, counter=0):
        """
        Define parameters to retry a push notification
        according to media_type.
        :param counter: `int` (optional) if retries was necessary
        because of connection fails

        Following rfc3261 specification, an exponential backoff factor is used.
        More specifically:
        backoff = 0.5
        T1 = 500ms
        max_retries_call = 7
        time_to_live_call = 64 seconds
        max_retries_sms = 11
        time_to_live_sms ~ 2 hours
        """

        retries = self.retries_params[self.media_type] - counter
        backoff_factor = self.retries_params['bo_factor'] * 0.5 * 2 ** counter

        status_forcelist = tuple([status for status in range(500, 600)])
        session = None

        session = session or requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def send_notification(self) -> dict:
        """
        Send a Firebase push notification
        """

        if self.error:
            self.log_error()
            return {'code': 500, 'body': {}, 'reason': 'Internal server error'}

        n_retries, backoff_factor = self.retries_params(self.wp_request.media_type)

        counter = 0
        error = False
        code = 500
        reason = ""
        body = None
        response = None

        while counter <= n_retries:

            self.log_request(path=self.pns.url_push)

            try:

                response = requests.post(self.pns.url_push,
                                         self.payload,
                                         headers=self.headers)
                break
            except requests.exceptions.RequestException as e:
                error = True
                reason = f'connection failed: {e}'
                counter += 1
                timer = backoff_factor * (2 ** (counter - 1))
                time.sleep(timer)

        if counter == n_retries:
            reason = "maximum retries reached"

        elif error:
            try:
                response = self.requests_retry_session(counter). \
                    post(self.pns.url_push,
                         self.payload,
                         headers=self.headers)
            except Exception as x:
                level = 'error'
                msg = f"outgoing {self.platform.title()} response for " \
                      f"{self.request_id}, push failed: " \
                      f"an error occurred in {x.__class__.__name__}"
                log_event(loggers=self.loggers, msg=msg, level=level)
        try:
            body = response.__dict__
        except (TypeError, ValueError):
            code = 500
            reason = 'cannot parse response body'
            body = {}
        else:
            reason = body.get('reason')
            code = response.status_code

        for k in ('raw', 'request', 'connection', 'cookies', 'elapsed'):
            try:
                del body[k]
            except KeyError:
                pass
            except TypeError:
                break

        body = json.dumps(fix_non_serializable_types(body))

        if isinstance(body, str):
            body = json.loads(body)

        keys = list(body.keys())
        for key in keys:
            if not body[key]:
                del body[key]

        results = {'body': body,
                   'code': code,
                   'reason': reason,
                   'url': self.pns.url_push,
                   'call_id': self.wp_request.call_id,
                   'token': self.token
                   }

        self.results = results
        self.log_results()

        # Request is missing required authentication credential.
        # Expected OAuth 2 access token, login cookie or other valid authentication
        # credential. UNAUTHENTICATED
        if code == 401 and reason == 'Unauthorized':
            try:
                if not self.pns.get('refreshed_token'):
                    level = 'warn'
                    msg = f"outgoing {self.platform.title()} response for request " \
                          f"{self.request_id} need a new access token - " \
                          f"server will refresh it and try again"
                    log_event(loggers=self.loggers, msg=msg, level=level, to_file=True)
                    # retry with a new Fireplace access token
                    self.pns.access_token = self.pns.set_access_token()
                    self.pns['refreshed_token'] = True
                    self.results = self.send_notification()

                return results
            except Exception as exc:
                level = 'error'
                msg = f"Filed trying to refresh access token"
                log_event(loggers=self.loggers, msg=msg, level=level, to_file=True)