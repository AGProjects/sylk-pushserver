import hashlib
import json
import logging
import socket
import ssl
import time

from ipaddress import ip_address

__all__ = ['callid_to_uuid', 'fix_non_serializable_types', 'resources_available', 'ssl_cert', 'try_again', 'check_host',
           'log_event', 'fix_device_id', 'fix_platform_name', 'log_incoming_request']


def callid_to_uuid(call_id: str) -> str:
    """

    Generate a UUIDv4 from a callId.

    UUIDv4 format: five segments of seemingly random hex data,
    beginning with eight hex characters, followed by three
    four-character strings, then 12 characters at the end.
    These segments are separated by a “-”.

    :param call_id: `str` Globally unique identifier of a call.
    :return: a str with a uuidv4.
    """
    hexa = hashlib.md5(call_id.encode()).hexdigest()

    uuidv4 = '%s-%s-%s-%s-%s' % \
             (hexa[:8], hexa[8:12], hexa[12:16], hexa[16:20], hexa[20:])

    return uuidv4


def fix_non_serializable_types(obj):
    """
    Converts a non serializable object in an appropriate one,
    if it is possible and in a recursive way.
    If not, return the str 'No JSON Serializable object'

    :param obj: obj to convert
    """
    if isinstance(obj, bytes):
        string = obj.decode()
        return fix_non_serializable_types(string)

    elif isinstance(obj, dict):
        return {
            fix_non_serializable_types(k): fix_non_serializable_types(v)
            for k, v in obj.items()
        }

    elif isinstance(obj, (tuple, list)):
        return [fix_non_serializable_types(elem) for elem in obj]

    elif isinstance(obj, str):
        try:
            dict_obj = json.loads(obj)
            return fix_non_serializable_types(dict_obj)
        except json.decoder.JSONDecodeError:
            return obj

    elif isinstance(obj, (bool, int, float)):
        return obj

    else:
        return


def resources_available(host: str, port: int) -> bool:
    """
    Check if a pair ip, port is available for a connection
    :param: `str` host
    :param: `int` port
    :return: a `bool` according to the test result.
    """
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if not host or not port:
        return None
    try:
        serversocket.bind((host, port))
        serversocket.close()
        return True
    except OSError:
        return False


def ssl_cert(cert_file: str, key_file=None) -> bool:
    """
    Check if a ssl certificate is valid.
    :param cert_file: `str` path to certificate file
    :param key_file: `str` path to key file
    :return: `bool` True for a valid certificate.
    """

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    try:
        ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        return True
    except (ssl.SSLError, NotADirectoryError, TypeError):
        return False


def try_again(timer: int, host: str, port: int,
              start_error: str, loggers: dict) -> None:
    """
    Sleep for a specific time and send log messages
    in case resources would not be available to start the app.
    :param timer: `int` time in seconds to wait (30 = DHCP delay)
    :param host: `str` IP address where app is trying to run
    :param port: `int` Host where app is trying to run
    :param start_error: `stṛ` Error msg to show in log.
    :param loggers: global logging instances to write messages (params.loggers)
    """
    timer = timer  # seconds, 30 for dhcp delay.
    level = 'error'
    msg = f"[can not init] on {host}:{port} - resources are not available"
    log_event(msg=start_error, level=level, loggers=loggers)
    log_event(msg=msg, level=level, loggers=loggers)
    msg = f'Server will try again in {timer} seconds'
    log_event(msg=msg, level=level, loggers=loggers)
    time.sleep(timer)


def check_host(host, allowed_hosts) -> bool:
    """
    Check if a host is in allowed_hosts
    :param host: `str` to check
    :return: `bool`
    """
    if not allowed_hosts:
        return True

    for subnet in allowed_hosts:
        if ip_address(host) in subnet:
            return True

    return False


def log_event(loggers: dict, msg: str, level: str = 'deb') -> None:
    """
    Write log messages into log file and in journal if specified.
    :param loggers: `dict` global logging instances to write messages (params.loggers)
    :param msg: `str` message to write
    :param level: `str` info, error, deb or warn
    :param to_file: `bool` write just in file if True
    """
    logger = loggers.get('to_journal')
    if logger.level != logging.DEBUG and loggers['debug'] is True:
        logger.setLevel(logging.DEBUG)
    elif logger.level != logging.INFO and loggers['debug'] is False:
        logger.setLevel(logging.INFO)

    if level == 'info':
        logger.info(msg)

    elif level == 'error':
        logger.error(msg)

    elif level == 'warn':
        logger.warning(msg)

    elif level in ('deb', 'debug'):
        logger.debug(msg)


def fix_device_id(device_id_to_fix: str) -> str:
    """
    Remove special characters from uuid
    :param device_id_to_fix: `str` uuid with special characters.
    :return: a `str` with fixed uuid.
    """
    if '>' in device_id_to_fix:
        uuid = device_id_to_fix.split(':')[-1].replace('>', '')
    elif ':' in device_id_to_fix:
        uuid = device_id_to_fix.split(':')[-1]
    else:
        uuid = device_id_to_fix
    device_id = uuid
    return device_id


def fix_platform_name(platform: str) -> str:
    """
    Fix platform name in case its value is 'android' or 'ios',
    replacing it for 'firebase' and 'apple'
    :param platform: `str` name of platform
    :return: a `str` with fixed name.
    """
    if platform in ('firebase', 'android', 'fcm'):
        return 'firebase'
    elif platform in ('apple', 'ios'):
        return 'apple'
    else:
        return platform


def fix_payload(body: dict) -> dict:
    payload = {}
    for item in body.keys():
        value = body[item]
        if item in ('sip_to', 'sip_from'):
            item = item.split('_')[1]
        else:
            item = item.replace('_', '-')
            payload[item] = value
    return payload


def pick_log_function(exc, *args, **kwargs):
    if ('rm_request' in exc.errors()[0]["loc"][1]):
        return log_remove_request(**kwargs)
    if ('add_request' in exc.errors()[0]["loc"][1]):
        return log_add_request(*args, **kwargs)
    else:
        return log_incoming_request(*args, **kwargs)


def log_add_request(task: str, host: str, loggers: dict,
                    request_id: str = None, body: dict = None,
                    error_msg: str = None) -> None:
    """
    Send log messages according to type of event.
    :param task: `str` type of event to log, can be
     'log_request', 'log_success' or 'log_failure'
    :param host: `str` client host where request comes from
    :param loggers: `dict` global logging instances to write messages (params.loggers)
    :param request_id: `str` request ID generated on request
    :param body: `dict` body of request
    :param error_msg: `str` to show in log
    """
    if task == 'log_request':
        payload = fix_payload(body)
        level = 'info'
        msg = f'{host} - Add Token - Request [{request_id}]: ' \
              f'{payload}'
        log_event(msg=msg, level=level, loggers=loggers)

    elif task == 'log_success':
        payload = fix_payload(body)
        msg = f'{host} - Add Token - Response [{request_id}]: ' \
              f'{payload}'
        level = 'info'
        log_event(msg=msg, level=level, loggers=loggers)

    elif task == 'log_failure':
        level = 'error'
        resp = error_msg
        msg = f'{host} - Add Token Failed - Response [{request_id}]: ' \
              f'{resp}'
        log_event(loggers=loggers, msg=msg, level=level)


def log_remove_request(task: str, host: str, loggers: dict,
                       request_id: str = None, body: dict = None,
                       error_msg: str = None) -> None:
    """
    Send log messages according to type of event.
    :param task: `str` type of event to log, can be
     'log_request', 'log_success' or 'log_failure'
    :param host: `str` client host where request comes from
    :param loggers: `dict` global logging instances to write messages (params.loggers)
    :param request_id: `str` request ID generated on request
    :param body: `dict` body of request
    :param error_msg: `str` to show in log
    """
    if task == 'log_request':
        payload = fix_payload(body)
        level = 'info'
        msg = f'{host} - Remove Token - Request [{request_id}]: ' \
              f'{payload}'
        log_event(msg=msg, level=level, loggers=loggers)

    elif task == 'log_success':
        payload = fix_payload(body)
        msg = f'{host} - Remove Token - Response [{request_id}]: ' \
              f'{payload}'
        level = 'info'
        log_event(msg=msg, level=level, loggers=loggers)

    elif task == 'log_failure':
        level = 'error'
        resp = error_msg
        msg = f'{host} - Remove Token Failed - Response {request_id}: ' \
              f'{resp}'
        log_event(loggers=loggers, msg=msg, level=level)


def log_push_request(task: str, host: str, loggers: dict,
                     request_id: str = None, body: dict = None,
                     error_msg: str = None) -> None:
    """
    Send log messages according to type of event.
    :param task: `str` type of event to log, can be
     'log_request', 'log_success' or 'log_failure'
    :param host: `str` client host where request comes from
    :param loggers: `dict` global logging instances to write messages (params.loggers)
    :param request_id: `str` request ID generated on request
    :param body: `dict` body of request
    :param error_msg: `str` to show in log
    """
    sip_to = body.get('to')
    event = body.get('event')

    if task == 'log_request':
        payload = fix_payload(body)
        level = 'info'
        msg = f'{host} - Push - Request [{request_id}]: ' \
              f'{event} for {sip_to} ' \
              f': {payload}'
        log_event(msg=msg, level=level, loggers=loggers)

    elif task == 'log_failure':
        level = 'error'
        resp = error_msg
        msg = f'{host} - Push Failed - Response [{request_id}]: ' \
              f'{resp}'
        log_event(loggers=loggers, msg=msg, level=level)


def log_incoming_request(task: str, host: str, loggers: dict,
                         request_id: str = None, body: dict = None,
                         error_msg: str = None) -> None:
    """
    Send log messages according to type of event.
    :param task: `str` type of event to log, can be
    'log_request', 'log_success' or 'log_failure'
    :param host: `str` client host where request comes from
    :param loggers: `dict` global logging instances to write messages (params.loggers)
    :param request_id: `str` request ID generated on request
    :param body: `dict` body of request
    :param error_msg: `str` to show in log
    """
    app_id = body.get('app_id')
    platform = body.get('platform')
    platform = platform if platform else ''
    sip_to = body.get('sip_to')
    device_id = body.get('device_id')
    device_id = fix_device_id(device_id) if device_id else None
    event = body.get('event')

    if task == 'log_request':
        payload = fix_payload(body)
        level = 'info'
        if sip_to:
            if device_id:
                msg = f'incoming {platform.title()} request {request_id}: ' \
                      f'{event} for {sip_to} using' \
                      f' device {device_id} from {host}: {payload}'
            else:
                msg = f'incoming {platform.title()} request {request_id}: ' \
                      f'{event} for {sip_to} ' \
                      f'from {host}: {payload}'
        elif device_id:
            msg = f'incoming {platform.title()} request {request_id}: ' \
                  f'{event} using' \
                  f' device {device_id} from {host}: {payload}'
        else:
            msg = f'incoming {platform.title()} request {request_id}: ' \
                  f' from {host}: {payload}'
        log_event(msg=msg, level=level, loggers=loggers)

    elif task == 'log_success':
        msg = f'incoming {platform.title()} response for {request_id}: ' \
              f'push accepted'
        level = 'info'
        log_event(msg=msg, level=level, loggers=loggers)

    elif task == 'log_failure':
        level = 'error'
        resp = error_msg
        msg = f'incoming {platform.title()} from {host} response for {request_id}, ' \
              f'push rejected: {resp}'
        log_event(loggers=loggers, msg=msg, level=level)
