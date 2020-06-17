

# To create a new app, import base classes from:

# this app is based on existing sylk app
# import json
# from pushserver.applications.sylk import *

# this app is based on existing linphone app
# import json
# from pushserver.applications.linphone import *

# this app is based on the base app
import json
from pushserver.applications.apple import *
from pushserver.applications.firebase import *


__all__ = ['AppleMyappHeaders', 'AppleMyappPayload',
           'FirebaseMyappHeaders', 'FirebaseMyappPayload']


class AppleMyappHeaders(AppleHeaders):
    """
    An Apple headers structure for a push notification


    @property
    def headers(self):
    """
        # Return: a valid dict of headers
    """
        data = {}
        headers = json.dumps(data)
        return headers
    """


class AppleMyappPayload(ApplePayload):
    """
    An Apple headers structure for a push notification

    @property
    def payload(self) -> dict:
    """
        # Return a valid payload:
    """
        data = {}
        payload = json.dumps(data)
        return payload
    """


class FirebaseMyappHeaders(FirebaseHeaders):
    """
    Firebase headers for a push notification


    @property
    def headers(self):
    """
        # Return: a valid dict of headers
    """
        data = {}
        headers = json.dumps(data)
        return headers
    """


class FirebaseMyAppPayload(FirebasePayload):
    """
    A payload for a Firebase push notification

    @property
    def payload(self) -> dict:
    """
        # Return a valid payload:
    """
        data = {}
        payload = json.dumps(data)
        return payload
    """