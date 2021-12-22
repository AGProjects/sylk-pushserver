import json
import os
import socket
import ssl
import time

import hyper
from hyper import HTTP20Connection, tls
from pushserver.models.requests import WakeUpRequest
from pushserver.pns.base import PNS, PushRequest, PlatformRegister
from pushserver.resources.utils import log_event, ssl_cert


class ApplePNS(PNS):
    """
    An Apple Push Notification service
    """

    def __init__(self, app_id: str, app_name: str, url_push: str,
                 voip: bool, cert_file: str, key_file: str):
        """
        :param app_id: `str`, blunde id provided by application.
        :param url_push: `str`, URI to push a notification (from applications.ini)
        :param cert_file `str`: path to APNS certificate (provided by dev app kit)
        :param key_file `str`: path to APNS key (provided by dev app kit)
        :param voip: `bool`, Required for apple, `True` for voip push notification type.
        """
        self.app_id = app_id
        self.app_name = app_name
        self.url_push = url_push
        self.voip = voip
        self.key_file = key_file
        self.cert_file = cert_file


class AppleConn(ApplePNS):
    """
    An Apple connection
    """

    def __init__(self, app_id: str, app_name: str, url_push: str,
                 voip: bool, cert_file: str, key_file: str,
                 apple_pns: PNS, loggers: dict, port: int = 443):
        """
        :param apple_pns `ApplePNS`: Apple Push Notification Service.
        :param port `int`: 443 or 2197 to allow APNS traffic but block other HTTP traffic.
        :param loggers: `dict` global logging instances to write messages (params.loggers)
        :attribute ssl_context `ssl.SSLContext`: generated with a valid apple certificate.
        :attribute connection `HTTP20Connection`: related to an app and its corresponding certificate.
        """
        self.app_id = app_id
        self.app_name = app_name
        self.url_push = url_push
        self.voip = voip
        self.key_file = key_file
        self.cert_file = cert_file
        self.apple_pns = apple_pns
        self.port = port
        self.loggers = loggers

    @property
    def ssl_context(self) -> ssl.SSLContext:
        """
        Define a ssl context using a cert_file to open a connection
        requires a valid certificate file

        :return: a ssl.SSLContext object
        """

        cert_file = self.cert_file
        key_file = self.key_file if self.key_file else self.cert_file

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        ssl_context.load_cert_chain(keyfile=key_file, certfile=cert_file)

        return ssl_context

    @property
    def connection(self) -> HTTP20Connection:
        """
        Open an apple connection
        requires a ssl context

        :return: an hyper.http20.connection.HTTP20Connection object
        """
        host = self.url_push
        port = self.port
        ssl_context = self.ssl_context

        connection = HTTP20Connection(host=host, port=port,
                                      ssl_context=ssl_context,
                                      force_proto=tls.H2C_PROTOCOL)

        cert_file_name = self.cert_file.split('/')[-1]
        key_file_name = self.key_file.split('/')[-1] if self.key_file else None

        if key_file_name:
            msg = f'{self.app_name.capitalize()} app: Connecting to {host}:{port} ' \
                  f'using {cert_file_name} certificate ' \
                  f'and {key_file_name} key files'
        else:
            msg = f'{self.app_name.capitalize()} app: Connecting to {host}:{port} ' \
                  f'using {cert_file_name} certificate'

        log_event(loggers=self.loggers, msg=msg, level='deb')

        return connection


class AppleRegister(PlatformRegister):
    def __init__(self, app_id: str, app_name: str, voip: bool,
                 credentials_path: str, config_dict: dict, loggers: dict):

        self.app_id = app_id
        self.app_name = app_name
        self.voip = voip
        self.credentials_path = credentials_path
        self.config_dict = config_dict
        self.loggers = loggers

        self.error = ''

    @property
    def url_push(self) -> str:
        try:
            return self.config_dict['apple_push_url']
        except KeyError:
            self.error = 'apple_push_url not found in applications.ini'
            return None

    @property
    def certificate(self) -> dict:
        if self.error:
            return {}
        else:
            try:
                cert_file = f"{self.credentials_path}/" \
                            f"{self.config_dict['apple_certificate']}"
                cert_exists = os.path.exists(cert_file)
                if not cert_exists:
                    self.error = f"{cert_file} - no such file."
                    return {}
                else:
                    return {'cert_file': cert_file, 'cert_exists': cert_exists}
            except KeyError:
                self.error = 'apple_certificate not found in applications.ini'
                return {}

    @property
    def key(self) -> dict:
        if self.error:
            return {}
        try:
            key_file = f"{self.credentials_path}/" \
                       f"{self.config_dict['apple_key']}"
            key_exists = os.path.exists(key_file)
            if not key_exists:
                self.error = f"{key_file} - no such file."
                return {}
        except KeyError:
            return {}
        return {'key_file': key_file, 'key_exists': key_exists}

    @property
    def ssl_valid_cert(self) -> bool:
        if self.error:
            return
        else:
            try:
                cert_file = self.certificate.get('cert_file')
                key_file = self.key.get('key_file')

                if not (cert_file or key_file):
                    self.error = 'An apple certificate/key is needed to open a connection'
                elif not ssl_cert(cert_file, key_file):
                    self.error = f"{cert_file} - bad ssl certificate."
                    return
                else:
                    return True
            except FileNotFoundError as exc:
                self.error = exc
                return

    @property
    def apple_pns(self) -> ApplePNS:
        if self.error:
            return

        if self.ssl_valid_cert:
            cert_file = self.certificate.get('cert_file')
            key_file = self.key.get('key_file')

            return ApplePNS(app_id=self.app_id,
                            app_name=self.app_name,
                            url_push=self.url_push,
                            voip=self.voip,
                            cert_file=cert_file,
                            key_file=key_file)

    @property
    def apple_conn(self):
        if self.error:
            return
        return AppleConn(app_id=self.app_id,
                         app_name=self.app_name,
                         url_push=self.url_push,
                         voip=self.voip,
                         cert_file=self.certificate.get('cert_file'),
                         key_file=self.key.get('key_file'),
                         apple_pns=self.apple_pns,
                         loggers=self.loggers).connection

    @property
    def register_entries(self):
        if self.error:
            return {}
        return {'pns': self.apple_pns,
                'conn': self.apple_conn}


class ApplePushRequest(PushRequest):
    """
    Apple push notification request
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
        self.platform = 'apple'
        self.request_id = request_id
        self.headers = headers
        self.payload = payload
        self.token = wp_request.token
        self.call_id = wp_request.call_id
        self.media_type = wp_request.media_type
        self.wp_request = wp_request
        self.loggers = loggers
        self.log_remote = log_remote

        self.apple_pns = register['pns']
        self.connection = register['conn']
        self.path = f'/3/device/{self.token}'

        self.results = self.send_notification()

    def send_notification(self) -> dict:
        """
        Send an apple push requests to a single device.
        If status of response is like 5xx,
        an exponential backoff factor is implemented
        to retry the notification according to media type.

        :param `hstr` token: destination device.
        :param `str` method: HTTP request method, must be 'POST'.
        :param `AppleHeaders` headers: Apple push notification headers.
        :param `ApplePayload` payload: Apple push notification payload.
        """

        if self.error:
            self.log_error()
            return {'code': 500, 'body': {},
                    'reason': 'Internal server error'}

        n_retries, backoff_factor = self.retries_params(self.media_type)

        log_path = f'http://{self.apple_pns.url_push}{self.path}'

        status_forcelist = tuple([status for status in range(500, 600)])

        counter = 0

        status = 500
        reason = ''
        body = {}

        while counter <= n_retries:
            if self.connection:
                try:
                    self.log_request(path=log_path)
                    self.connection.request('POST', self.path,
                                            self.payload,
                                            self.headers)

                    response = self.connection.get_response()
                    reason_str = response.read().decode('utf8').replace("'", '"')

                    if reason_str:
                        reason_json = json.loads(reason_str)
                        reason = reason_json.get('reason')
                    else:
                        reason = reason_str

                    status = response.status

                    if status not in status_forcelist:
                        break

                except socket.gaierror:
                    reason = 'socket error'

                except hyper.http20.exceptions.StreamResetError:
                    reason = 'stream error'

                except ValueError as err:
                    reason = f'Bad type of object in headers or payload: {err}'
                    break
            else:
                reason = 'no connection'

            counter += 1
            timer = backoff_factor * (2 ** (counter - 1))
            time.sleep(timer)

        if counter == n_retries:
            reason = 'max retries reached'

        url = f'https:{self.connection.host}:{self.connection.port}{self.path}'

        if status != 200:
            details = self.apple_error_info(reason)
            if details:
                reason = f'{reason} - {details}'

        if status == 400 and 'BadDeviceToken' in reason:
            status = 410

        results = {'body': body,
                   'code': status,
                   'reason': reason,
                   'url': url,
                   'platform': 'apple',
                   'call_id': self.call_id,
                   'token': self.token
                   }

        self.results = results
        self.log_results()
        return results

    def apple_error_info(self, reason):
        """
        Give a human readable message according to 'reason' from apple APN.
        :returns : a string with message according to reason
        """

        description_codes = {'ConnectionFailed': 'There was an error connecting to APNs.',
                             'InternalException': 'This exception should not be raised. If it is, please report this as a bug.',
                             'BadPayloadException': 'Something bad with the payload.',
                             'BadCollapseId': 'The collapse identifier exceeds the maximum allowed size',
                             'BadDeviceToken': 'The specified device token was bad. Verify that the request contains a valid token and that the token matches the environment.',
                             'BadExpirationDate:': 'The apns-expiration value is bad.',
                             'BadMessageId': 'The apns-id value is bad.',
                             'BadPriority': 'The apns-priority value is bad.',
                             'BadTopic': 'The apns-topic was invalid.',
                             'DeviceTokenNotForTopic': 'The device token does not match the specified topic.',
                             'DuplicateHeaders': 'One or more headers were repeated.',
                             'IdleTimeout': 'Idle time out.',
                             'MissingDeviceToken': 'The device token is not specified in the request :path. Verify that the :path header contains the device token.',
                             'MissingTopic': 'The apns-topic header of the request was not specified and was required. The apns-topic header is mandatory when the client is connected using a certificate that supports multiple topics.',
                             'PayloadEmpty': 'The message payload was empty.',
                             'TopicDisallowed': 'Pushing to this topic is not allowed.',
                             'BadCertificate': 'The certificate was bad.',
                             'BadCertificateEnvironment': 'The client certificate was for the wrong environment.',
                             'ExpiredProviderToken': 'The provider token is stale and a new token should be generated.',
                             'Forbidden': 'The specified action is not allowed.',
                             'InvalidProviderToken': 'The provider token is not valid or the token signature could not be verified.',
                             'MissingProviderToken': 'No provider certificate was used to connect to APNs and Authorization header was missing or no provider token was specified.',
                             'BadPath': 'The request contained a bad :path value.',
                             'MethodNotAllowed': 'The specified :method was not POST.',
                             'Unregistered': 'The device token is inactive for the specified topic.',
                             'PayloadTooLarge': 'The message payload was too large. The maximum payload size is 4096 bytes.',
                             'TooManyProviderTokenUpdates': 'The provider token is being updated too often.',
                             'TooManyRequests': 'Too many requests were made consecutively to the same device token.',
                             'InternalServerError': 'An internal server error occurred.',
                             'ServiceUnavailable': 'The service is unavailable.',
                             'Shutdown': 'The server is shutting down.',
                             'InvalidPushType': 'The apns-push-type value is invalid.'}
        try:
            message = description_codes[reason]
            return message
        except KeyError:
            return None

