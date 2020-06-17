import json

from pushserver.resources import settings

__all__ = ['FirebaseHeaders', 'FirebasePayload']


class FirebaseHeaders(object):
    def __init__(self, app_id: str, event: str, token: str,
                 call_id: str, sip_from: str, from_display_name: str,
                 sip_to: str, media_type: str, silent: bool):
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
        self.access_token = ''

        self.auth_key = \
            settings.params.pns_register[(self.app_id, 'firebase')]['auth_key']
        if not self.auth_key:
            pns_dict = settings.params.pns_register[(self.app_id, 'firebase')]['pns'].__dict__
            self.access_token = pns_dict['access_token']

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
                 sip_to: str, media_type: str, silent: bool):
        """
        :param token: `str` destination device token (required for sylk-apple)
        :param call_id: `str` unique SIP session id for each call
        :param event: `str` 'incoming_session', 'incoming_conference', 'cancel'
        :param media_type: `str` 'audio', 'video', 'chat', 'sms' or 'file-transfer'
        :param sip_from: `str` originator of the sip call.
        :param from_display_name: `str`
        :param sip_to: `str` destination uri
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

    @property
    def payload(self) -> dict:
        """
        Generate a Firebase payload for a push notification

        :return a Firebase payload:
        """
        payload = {}
        return payload
