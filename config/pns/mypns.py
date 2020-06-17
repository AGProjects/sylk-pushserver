

# To create a new app, import base classes from:

# this app is based on existing apple pns
# from pushserver.pns.apple import *

# this app is based on existing firebase pns
# from pushserver.pns.firebase import *

# this app is based on the base pns
from pushserver.pns.base import *


__all__ = ['MyPnsPNS', 'MyPnsRegister']


class MyPnsPNS(PNS):
    """
    A Push Notification service
    """


class MyPnsRegister(PlatformRegister):
    """
    A register with pns and other needed objects


    @property
    def register_entries(self):

        return {'pns': self.pns,
                ...,
                }
"""