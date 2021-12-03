import importlib
import json

from pushserver.models.requests import WakeUpRequest
from pushserver.resources import settings


def handle_request(wp_request, request_id: str) -> dict:
    """
    Create a PushNotification object,
    and call methods to send the notification.

    :param wp_request: `WakeUpRequest', received from /push route.
    :param loggers: `dict` global logging instances to write messages (params.loggers)
    :param request_id: `str`, request ID generated on request event.
    :return: a `dict` with push notification results
    """
    push_notification = PushNotification(wp_request=wp_request, request_id=request_id)
    results = push_notification.send_notification()
    return results


class PushNotification(object):
    """
    Push Notification actions from wake up request
    """

    def __init__(self, wp_request: WakeUpRequest, request_id: str):
        """
        :param wp_request: `WakeUpRequest`, from http request
        :param request_id: `str`, request ID generated on request event.
        """
        self.wp_request = wp_request
        self.app_id = self.wp_request.app_id
        self.platform = self.wp_request.platform
        self.pns_register = settings.params.pns_register
        self.request_id = request_id
        self.loggers = settings.params.loggers
        self.log_remote = self.pns_register[(self.app_id, self.platform)].get('log_remote')
        self.config_dict = self.pns_register[(self.app_id, self.platform)]

        self.app_name = self.pns_register[(self.app_id, self.platform)]['name']

        self.args = [self.app_id, self.wp_request.event, self.wp_request.token,
                     self.wp_request.call_id, self.wp_request.sip_from,
                     self.wp_request.from_display_name, self.wp_request.sip_to,
                     self.wp_request.media_type, self.wp_request.silent,
                     self.wp_request.reason, self.wp_request.badge]

    @property
    def custom_apps(self):
        apps = [self.pns_register[key]['name'] for key in self.pns_register.keys()]
        custom_apps = set(app for app in apps if app not in ('sylk', 'linphone'))
        return custom_apps

    def send_notification(self) -> dict:
        """
        Send a push notification according to wakeup request params.
        """
        error = ''
        headers_class = self.pns_register[(self.app_id, self.platform)]['headers_class']
        headers = headers_class(*self.args).headers

        payload_class = self.pns_register[(self.app_id, self.platform)]['payload_class']
        payload_dict = payload_class(*self.args).payload
        try:
            payload = json.dumps(payload_dict)
        except Exception:
            payload = None

        if not (headers and payload):
            error = f'{headers_class.__name__} and {payload_class.__name__} ' \
                    f'returned bad objects:' \
                    f'{headers}, {payload}'

        if not isinstance(headers, dict) or not isinstance(payload, str):
            error = f'{headers_class.__name__} and {payload_class.__name__} ' \
                    f'returned bad objects:' \
                    f'{headers}, {payload}'

        register = self.pns_register[(self.app_id, self.platform)]
        platform_module = importlib.import_module(f'pushserver.pns.{self.platform}')

        push_request_class = getattr(platform_module,
                                     f'{self.platform.capitalize()}PushRequest')

        push_request = push_request_class(error=error,
                                          app_name=self.app_name,
                                          app_id=self.app_id,
                                          request_id=self.request_id,
                                          headers=headers,
                                          payload=payload,
                                          loggers=self.loggers,
                                          log_remote=self.log_remote,
                                          wp_request=self.wp_request,
                                          register=register)
        return push_request.results
