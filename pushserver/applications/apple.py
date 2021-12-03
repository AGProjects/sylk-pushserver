__all__ = ['AppleHeaders', 'ApplePayload']


class AppleHeaders(object):
    """
    Apple headers structure for a push notification
    """

    def __init__(self, app_id: str, event: str, token: str,
                 call_id: str, sip_from: str, from_display_name: str,
                 sip_to: str, media_type: str, silent: bool, reason: str,
                 badge: int):
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
        :param badge: `int` Number to display as badge
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
        self.badge = badge

        self.apns_push_type = self.create_push_type()
        self.apns_expiration = self.create_expiration()
        self.apns_topic = self.create_topic()
        self.apns_priority = self.create_priority()

    def create_push_type(self) -> str:
        """
        logic to define apns_push_type value using request parameters
        apns_push_type reflect the contents of the notification’s payload,
        it can be:
        'alert', 'background', 'voip',
        'complication', 'fileprovider' or 'mdm'.
        """
        return

    def create_expiration(self) -> int:
        """
        logic to define apns_expiration value using request parameters
        apns_expiration is the date at which the notification expires,
        (UNIX epoch expressed in seconds UTC).
        """
        return

    def create_topic(self) -> str:
        """
        logic to define apns_topic value using request parameters
        apns_topic is in general is the app’s bundle ID and may have
        a suffix based on the notification’s type.
        """
        return

    def create_priority(self) -> int:
        """
        logic to define apns_priority value using request parameters
        Notification priority,
        apns_prioriy 10 o send the notification immediately,
        5 to send the notification based on power considerations
        on the user’s device.
        """
        return

    @property
    def headers(self) -> dict:
        """
        Generate apple notification headers

        :return: a `dict` object with headers.
        """

        headers = {
            'apns-push-type': self.apns_push_type,
            'apns-expiration': self.apns_expiration,
            'apns-priority': self.apns_priority,
            'apns-topic': self.apns_topic,
            'authorization': f"bearer {self.token}"}

        if self.apns_push_type == 'background':
            headers['content-available'] = '1'

        return headers


class ApplePayload(object):
    """
    Apple payload structure for a push notification
    """

    def __init__(self, app_id: str, event: str, token: str,
                 call_id: str, sip_from: str, from_display_name: str,
                 sip_to: str, media_type, silent: bool, reason: str,
                 badge: int):
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
        :param badge: `int` Number to display as badge
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
        self.badge = badge

    @property
    def payload(self) -> dict:
        """
        logic to define apple payload using request parameters
        """

        payload = {}
        return payload

