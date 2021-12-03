import json

from pushserver.resources import settings
from oauth2client.service_account import ServiceAccountCredentials

__all__ = ['FirebaseHeaders', 'FirebasePayload']


class FirebaseHeaders(object):
    def __init__(self, app_id: str, event: str, token: str,
                 call_id: str, sip_from: str, from_display_name: str,
                 sip_to: str, media_type: str, silent: bool, reason: str):
        """
        :param app_id: `str` id provided by the mobile application (bundle id)
        :param event: `str` 'incoming_session', 'incoming_conference' or 'cancel'
        :param token: `str` destination device token.
        :param call_id: `str` unique sip parameter.
        :param sip_from: `str` SIP URI for who is calling
        :param from_display_name: `str` display name of the caller
        :param sip_to: `str` SIP URI for who is called
        :param media_type: `str` 'audio', 'video', 'chat', 'sms' or 'file-transfer'
        :param silent: `bool` True for silent notification
        """

        self.app_id = app_id
        self.token = token
        self.call_id = call_id
        self.sip_from = sip_from
        self.sip_to = sip_to
        self.from_display_name = from_display_name
        self.media_type = media_type
        self.silent = silent
        self.event = event
        self.reason = reason
        
        try:
            self.auth_key = settings.params.pns_register[(self.app_id, 'firebase')]['auth_key']
        except KeyError:
            self.auth_key = None

        try:
            self.auth_file = settings.params.pns_register[(self.app_id, 'firebase')]['auth_file']
        except KeyError:
            self.auth_file = None

    @property
    def access_token(self) -> str:
        # https://github.com/firebase/quickstart-python/blob/909f39e77395cb0682108184ba565150caa68a31/messaging/messaging.py#L25-L33

        """
        Retrieve a valid access token that can be used to authorize requests.
        :return: `str` Access token.
        """
        scopes = ['https://www.googleapis.com/auth/firebase.messaging']
        try:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(self.auth_file, scopes)
            access_token_info = credentials.get_access_token()
            return access_token_info.access_token
        except Exception as e:
            self.error = f"Error: cannot generated Firebase access token: {e}"
            return ''

    @property
    def headers(self):
        """
        Generate Firebase headers structure for a push notification

        :return: a firebase push notification header.
        """
        if self.auth_key:
            headers = {'Content-Type': 'application/json',
                       'Authorization': f"key={self.auth_key}"}
        else:
            headers = {
                'Authorization': f"Bearer {self.access_token}",
                'Content-Type': 'application/json; UTF-8',
            }

        return headers


class FirebasePayload(object):
    def __init__(self, app_id: str, event: str, token: str,
                 call_id: str, sip_from: str, from_display_name: str,
                 sip_to: str, media_type: str, silent: bool, reason: str):
        """
        :param app_id: `str` id provided by the mobile application (bundle id)
        :param event: `str` 'incoming_session', 'incoming_conference', 'cancel' or 'message'
        :param token: `str` destination device token.
        :param call_id: `str` unique sip parameter.
        :param sip_from: `str` SIP URI for who is calling
        :param from_display_name: `str` display name of the caller
        :param sip_to: `str` SIP URI for who is called
        :param media_type: `str` 'audio', 'video', 'chat', 'sms' or 'file-transfer'
        :param silent: `bool` True for silent notification
        :param reason: `str` Cancel reason
        """
        self.app_id = app_id
        self.token = token
        self.call_id = call_id  # corresponds to session_id in the output
        self.event = event
        self.media_type = media_type
        self.sip_from = sip_from
        self.from_display_name = from_display_name
        self.sip_to = sip_to
        self.silent = silent
        self.reason = reason

    @property
    def payload(self) -> dict:
        """
        Generate a Firebase payload for a push notification

        :return a Firebase payload:
        """
        payload = {}
        return payload
