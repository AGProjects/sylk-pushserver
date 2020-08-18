import concurrent
import datetime
import json
import socket

import requests

from pushserver.resources.utils import log_event


class PNS(object):
    """
    Push Notification Service
    """

    def __init__(self, app_id: str, app_name: str, url_push: str, voip: bool = False):
        """
        :param app_id: `str`, Id provided by application.
        :param app_name: `str`, Application name.
        :param url_push: `str`, URI to push a notification.
        :param voip: `bool`, Required for apple, `True` for voip push notification type.
        """
        self.app_id = app_id
        self.app_name = app_name
        self.url_push = url_push
        self.voip = voip


class PlatformRegister(object):
    def __init__(self, config_dict, credentials_path: str, loggers: dict):

        self.credentials_path = credentials_path
        self.config_dict = config_dict
        self.loggers = loggers


class PushRequest(object):

    def __init__(self, error: str, app_name: str, app_id: str, platform: str,
                 request_id: str, headers: str, payload: dict, token: str,
                 media_type: str, loggers: dict, log_remote: dict, wp_request: dict):

        self.error = error
        self.app_name = app_name
        self.app_id = app_id
        self.platform = platform
        self.request_id = request_id
        self.headers = headers
        self.payload = payload
        self.token = token
        self.media_type = media_type
        self.loggers = loggers
        self.log_remote = log_remote
        self.wp_request = wp_request

    results = {}

    def retries_params(self, media_type: str) -> tuple:
        if not media_type or media_type == 'sms':
            n_tries = 11
        else:
            n_tries = 7
        bo_factor = 0.5

        return n_tries, bo_factor

    def log_request(self, path: str) -> None:
        """
        Write in log information about push notification,
        using log_event function

        :param path: `str`, path where push notification will be sent.
        :param app_name: `str` for friendly log.
        :param platform: `str`, 'apple' or 'firebase'.
        :param request_id: `str`, request ID generated on request event.
        :param headers: `json`, of push notification.
        :param payload: `json`, of push notification.
        :param loggers: `dict` global logging instances to write messages (params.loggers)
        """

        # log_app_name = app_name.capitalize()
        log_platform = self.platform.capitalize()

        log_path = path if path else self.path

        level = 'info'
        msg = f'outgoing {log_platform} request {self.request_id} to {log_path}'
        log_event(loggers=self.loggers, msg=msg, level=level)

        if self.loggers['debug']:
            level = 'deb'
            msg = f'outgoing {log_platform} request {self.request_id} to {log_path}'
            log_event(loggers=self.loggers, msg=msg, level=level, to_file=True)

            msg = f'outgoing {log_platform} request {self.request_id} headers: {self.headers}'
            log_event(loggers=self.loggers, msg=msg, level=level, to_file=True)

            msg = f'outgoing {log_platform} request {self.request_id} body: {self.payload}'
            log_event(loggers=self.loggers, msg=msg, level=level, to_file=True)

    def log_error(self):
        level = 'error'
        msg = f"outgoing {self.platform.title()} response for " \
              f"{self.request_id}, push failed: " \
              f"{self.error}"
        log_event(loggers=self.loggers, msg=msg, level=level)

    def server_ip(self, destination):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((destination, 1))
            return s.getsockname()[0]
        except socket.error:
            return None

    def log_remotely(self, body: dict, code: str, reason: str, url: str) -> None:
        """
        Fork a log of a payload incoming request to a remote url
        :param body: `dict` response to push request
        :param code: `int` of response to push request
        :param reason: `str` of response to push request
        """

        push_response = {'code': code, 'description': reason, 'push_url': url}
        headers = {'Content-Type': 'application/json'}
        server_ip = self.server_ip('1.2.3.4')
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        payload = {'request': body, 'response': push_response,
                   'server_ip': server_ip,'timestamp': timestamp}

        task = 'log remote'

        log_key = self.log_remote.get('log_key')
        log_time_out = self.log_remote.get('log_time_out')

        results = []

        for log_url in self.log_remote['log_urls']:
            if self.loggers['debug']:
                msg = f'{task} request {self.request_id} to {log_url}'
                log_event(loggers=self.loggers, msg=msg, level='info')
                msg = f'{task} request {self.request_id} to {log_url} headers: {headers}'
                log_event(loggers=self.loggers, msg=msg, level='info', to_file=True)
                msg = f'{task} request {self.request_id} to {log_url} body: {payload}'
                log_event(loggers=self.loggers, msg=msg, level='info', to_file=True)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(
                        lambda: requests.post(url=log_url,
                                              json=payload,
                                              headers=headers,
                                              timeout=log_time_out or 2)
                    )
                    for log_url in self.log_remote['log_urls']
                ]

            results = [
                f.result()
                for f in futures
            ]
        except requests.exceptions.ConnectionError as exc:
            if self.loggers['debug']:
                msg = f'{task} for {self.request_id}: connection error {exc}'
                log_event(loggers=self.loggers, msg=msg, level='error')
                log_event(loggers=self.loggers, msg=msg, level='error', to_file=True)
        except requests.exceptions.ReadTimeout as exc:
            if self.loggers['debug']:
                msg = f'{task} for {self.request_id}: connection error {exc}'
                log_event(loggers=self.loggers, msg=msg, level='error')
                log_event(loggers=self.loggers, msg=msg, level='error', to_file=True)

        if not results:
            return

        for url, result in list(zip(self.log_remote['log_urls'], results)):
            code = result.status_code
            text = result.text[:500]

            if log_key:
                try:
                    result = result.json()
                    value = result.get(log_key)
                except (json.decoder.JSONDecodeError, AttributeError):
                    value = {}

                if value:

                    if self.loggers['debug']:
                        msg = f'{task} response for request {self.request_id} from {url} - ' \
                              f'{code} {log_key}: {value}'
                        log_event(loggers=self.loggers, msg=msg, level='info')
                        log_event(loggers=self.loggers, msg=msg, level='info', to_file=True)

                else:
                    if self.loggers['debug']:
                        msg = f'{task} response for request {self.request_id} - ' \
                              f'code: {code}, key not found'
                        log_event(loggers=self.loggers, msg=msg, level='error')

                        msg = f'{task} response for request {self.request_id} - ' \
                              f'{log_key} key not found in: {text}'
                        log_event(loggers=self.loggers, msg=msg, level='error', to_file=True)

            else:

                if self.loggers['debug']:
                    msg = f'{task} code response for request {self.request_id} ' \
                          f'from {url}: {code}'
                    log_event(loggers=self.loggers, msg=msg, level='info')
                    msg = f'{task} response for request {self.request_id} ' \
                          f'from {url}: {code} {text}'
                    log_event(loggers=self.loggers, msg=msg, level='info', to_file=True)

    def log_results(self):
        """
        Log to journal system the result of push notification
        """
        body = self.results['body']
        code = self.results['code']
        reason = self.results['reason']
        url = self.results['url']

        if self.loggers['debug']:
            level = 'info'
            body = json.dumps(body)
            msg = f"outgoing {self.platform.title()} response for request " \
                  f"{self.request_id} body: {body}"
            log_event(loggers=self.loggers, msg=msg, level=level, to_file=True)

        if code == 200:
            level = 'info'
            msg = f"outgoing {self.platform.title()} response for request " \
                  f"{self.request_id}: push notification sent successfully"
            log_event(loggers=self.loggers, msg=msg, level=level)
        else:
            level = 'error'
            msg = f"outgoing {self.platform.title()} response for " \
                  f"{self.request_id}, push failed with code {code}: {reason}"
            log_event(loggers=self.loggers, msg=msg, level=level)

        body = {'incoming_body': self.wp_request.__dict__,
                'outgoing_headers': self.headers,
                'outgoing_body': self.payload
                }

        if self.log_remote.get('log_urls'):
            self.log_remotely(body=body, code=code, reason=reason, url=url)
