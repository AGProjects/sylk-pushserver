from pydantic import BaseModel, root_validator, validator

from pushserver.resources import settings
from pushserver.resources.utils import fix_platform_name


def gen_validator_items() -> tuple:
    """
    Generate some dicts according to minimum required parameters,
    and each app required paramaters, usefull for request validation.
    :return: two `dict` objects with common items and apps items.
    """

    common_items = {'app-id', 'call-id',
                    'platform', 'from', 'token'}

    only_sylk_items = {'silent', 'to', 'event'}
    only_linphone_items = set()

    apps_items = {'sylk': common_items | only_sylk_items,  # union
                  'linphone': common_items | only_linphone_items}

    return common_items, apps_items


common_items, apps_items = gen_validator_items()


def alias_rename(attribute: str) -> str:
    """
    Rename request name attribute, replacing '_' by '_'
    and removing 'sip_' characters.
    :param attribute: `str` from request
    :return: a `str` corresponding to alias.
    """
    if attribute.startswith('sip_'):
        return attribute.split('_', maxsplit=1)[1]
    return attribute.replace('_', '-')


class AddRequest(BaseModel):
    app_id: str                    # id provided by the mobile application (bundle id)
    platform: str                  # 'firebase', 'android', 'apple' or 'ios'
    token: str                     # destination device token in hex
    device_id: str                 # the device-id that owns the token (used for logging purposes)
    silent: bool = True
    user_agent: str = None

    class Config:
        alias_generator = alias_rename

    @root_validator(pre=True)
    def check_required_items_for_add(cls, values):

        app_id, platform = values.get('app-id'), values.get('platform')

        if not app_id:
            raise ValueError("Field 'app-id' required")
        if not platform:
            raise ValueError("Field 'platform' required")

        platform = fix_platform_name(platform)

        if platform not in ('firebase', 'apple'):
            raise ValueError(f"The '{platform}' platform is not configured")

        pns_register = settings.params.pns_register

        if (app_id, platform) not in pns_register.keys():
            raise ValueError(f"{platform.capitalize()} {app_id} app "
                             f"is not configured")
        return values

    @validator('platform')
    def platform_valid_values(cls, v):
        if v not in ('apple', 'ios', 'android', 'firebase', 'fcm', 'apns'):
            raise ValueError("platform must be 'apple', 'android' or 'firebase'")
        return v


class AddResponse(BaseModel):
    app_id: str                    # id provided by the mobile application (bundle id)
    platform: str                  # 'firebase', 'android', 'apple' or 'ios'
    token: str                     # destination device token in hex
    device_id: str                 # the device-id that owns the token (used for logging purposes)
    silent: bool = True
    user_agent: str = None

    class Config:
        allow_population_by_field_name = True
        alias_generator = alias_rename


class RemoveRequest(BaseModel):
    app_id: str                    # id provided by the mobile application (bundle id)
    device_id: str = None          # the device-id that owns the token (used for logging purposes)

    class Config:
        alias_generator = alias_rename

    @root_validator(pre=True)
    def check_required_items_for_add(cls, values):

        app_id = values.get('app-id')

        if not app_id:
            raise ValueError("Field 'app-id' required")

        return values


class RemoveResponse(BaseModel):
    app_id: str                    # id provided by the mobile application (bundle id)
    device_id: str = None          # the device-id that owns the token (used for logging purposes)

    class Config:
        allow_population_by_field_name = True
        alias_generator = alias_rename


class PushRequest(BaseModel):
    event: str = None              # (required for sylk) 'incoming_session', 'incoming_conference' or 'cancel'
    call_id: str                   # (required for apple) unique sip parameter
    sip_from: str                  # (required for firebase) SIP URI for who is calling
    from_display_name: str = None  # (required for sylk) display name of the caller
    to: str                        # SIP URI for who is called
    media_type: str = None         # 'audio', 'video', 'chat', 'sms' or 'file-transfer'
    reason: str = None             # Cancel reason
    badge: int = 1

    class Config:
        alias_generator = alias_rename


class WakeUpRequest(BaseModel):
    # API expects a json object like:
    app_id: str                    # id provided by the mobile application (bundle id)
    platform: str                  # 'firebase', 'android', 'apple' or 'ios'
    event: str = None              # (required for sylk) 'incoming_session', 'incoming_conference', 'cancel' or 'message'
    token: str                     # destination device token in hex
    device_id: str = None          # the device-id that owns the token (used for logging purposes)
    call_id: str                   # (required for apple) unique sip parameter
    sip_from: str                  # (required for firebase) SIP URI for who is calling
    from_display_name: str = None  # (required for sylk) display name of the caller
    sip_to: str                    # SIP URI for who is called
    media_type: str = None         # 'audio', 'video', 'chat', 'sms' or 'file-transfer'
    silent: bool = True            # True for silent notification
    reason: str = None             # Cancel reason
    badge: int = 1

    class Config:
        alias_generator = alias_rename

    @root_validator(pre=True)
    def check_required_items_by_app(cls, values):

        app_id, platform = values.get('app-id'), values.get('platform')

        if not app_id:
            raise ValueError("Field 'app-id' required")
        if not platform:
            raise ValueError("Field 'platform' required")

        platform = fix_platform_name(platform)

        if platform not in ('firebase', 'apple'):
            raise ValueError(f"'{platform}' platform is not configured")

        pns_register = settings.params.pns_register

        if (app_id, platform) not in pns_register.keys():
            raise ValueError(f"{platform.capitalize()} {app_id} app "
                             f"is not configured")

        try:
            name = pns_register[(app_id, platform)]['name']
            check_items = apps_items[name]
            missing_items = []

            for item in check_items:
                if values.get(item) is None:
                    missing_items.append(item)
            if missing_items:
                missing_items_show = []
                for item in missing_items:
                    if item in ('sip_to', 'sip_from', 'device_id'):
                        item = item.split('_')[1]
                    else:
                        item = item.replace('-', '_')
                    missing_items_show.append(item)

                raise ValueError(f"'{' ,'.join(missing_items)}' "
                                 f"item(s) missing.")
        except KeyError:
            pass

        event = values.get('event')
        if event != 'cancel':
            media_type = values.get('media-type')
            if not media_type:
                raise ValueError("Field media-type required")
            if media_type not in ('audio', 'video', 'chat', 'sms', 'file-transfer'):
                raise ValueError("media-type must be 'audio', 'video', "
                                 "'chat', 'sms', 'file-transfer'")
        if 'linphone' in name:
            if event:
                if event != 'incoming_session':
                    raise ValueError('event not found (must be incoming_sesion)')
            else:
                values['event'] = 'incoming_session'
        return values

    @validator('platform')
    def platform_valid_values(cls, v):
        if v not in ('apple', 'ios', 'android', 'firebase'):
            raise ValueError("platform must be 'apple', 'android' or 'firebase'")
        return v

    @validator('event')
    def event_valid_values(cls, v):
        if v not in ('incoming_session', 'incoming_conference_request', 'cancel', 'message'):
            raise ValueError("event must be 'incoming_session', 'incoming_conference_request', 'cancel' or 'message'")
        return v
