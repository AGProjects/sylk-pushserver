from datetime import datetime

from pushserver.applications.apple import *
from pushserver.applications.firebase import *

__all__ = ['AppleLinphoneHeaders', 'AppleLinphonePayload',
           'FirebaseLinphoneHeaders', 'FirebaseLinphonePayload']


class AppleLinphoneHeaders(AppleHeaders):
    """
    An Apple headers structure for a push notification
    """

    def create_push_type(self) -> str:
        """
        logic to define apns_push_type value using request parameters
        apns_push_type reflect the contents of the notification’s payload,
        it can be:
        'alert', 'background', 'voip',
        'complication', 'fileprovider' or 'mdm'.
        """
        return 'voip'

    def create_expiration(self) -> int:
        """
        logic to define apns_expiration value using request parameters
        apns_expiration is the date at which the notification expires,
        (UNIX epoch expressed in seconds UTC).
        """
        return '10'

    def create_topic(self) -> str:
        """
        Define a valid apns topic
        based on app_id value, without 'prom' or 'dev'

        :return: a `str` with a valid apns topic
        """

        if self.app_id.endswith('.dev') or self.app_id.endswith('.prod'):
            apns_topic = '.'.join(self.app_id.split('.')[:-1])
        else:
            apns_topic = self.app_id
        if not '.voip' in apns_topic:
            apns_topic = f"{apns_topic}.voip"

        return apns_topic

    def create_priority(self) -> int:
        """
        logic to define apns_priority value using request parameters
        Notification priority,
        apns_prioriy 10 o send the notification immediately,
        5 to send the notification based on power considerations
        on the user’s device.
        """
        return '10'


class FirebaseLinphoneHeaders(FirebaseHeaders):
    """
    Firebase headers for a push notification
    """


class AppleLinphonePayload(ApplePayload):
    """
    An Apple payload for a Linphone push notification
    """

    @property
    def payload(self) -> dict:
        """
        Generate apple notification payload

        :param silent: `bool` True for silent notification.
        :return: A `json` with a push notification payload.

        """

        now = datetime.now()
        send_time = now.strftime('%Y-%m-%d %H:%M:%S')

        if self.silent:
            payload = {'aps': {'sound': '',
                               'loc-key': 'IC_SIL',
                               'call-id': self.call_id,
                               'send-time': send_time},
                       'from-uri': self.sip_from,
                       'pn_ttl': 2592000}
        else:
            payload = {'aps': {'alert': {'loc-key': 'IC_MSG',
                                         'loc-args': self.sip_from},
                               'sound': 'msg.caf', 'badge': 1},
                       'pn_ttl': 2592000,
                       'call-id': self.call_id,
                       'send-time': send_time}

        return payload


class FirebaseLinphonePayload(FirebasePayload):
    """
    A Firebase payload for a Linphone push notification
    """

    @property
    def payload(self) -> dict:
        """
        Generate a Firebase payload for a push notification

        :return a Firebase payload:
        """

        now = datetime.now()
        send_time = now.strftime('%Y-%m-%d %H:%M:%S')

        payload = {'to': self.token,
                   'time_to_live': 2419199,
                   'priority': 'high',
                   'data': {'call-id': self.call_id,
                            'sip-from': self.sip_from,
                            'loc-key': '',
                            'loc-args': self.sip_from,
                            'send-time': send_time}}
        return payload

