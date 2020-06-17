import configparser
import importlib
import os
import sys

from pushserver.resources.utils import log_event


def check_apps_classes(name: str, platform: str, extra_dir: str) -> tuple:
    """
    Check for custom classes
    :param name: `str` name of custom app, which corresponds to module
    :param platform: `str` 'apple' or 'firebase'
    :param extra_dir: `str` path to extra applications dir
    :return: a tuple with, error (str), headers_class (class), payload_class (class)
    """

    # Check for known apps:
    try:
        module = importlib.import_module(f'pushserver.applications.{name.lower()}')
        headers_class_name = f'{platform.capitalize()}{name.lower().capitalize()}Headers'
        headers_class = getattr(module, headers_class_name)

        payload_class_name = f'{platform.capitalize()}{name.lower().capitalize()}Payload'
        payload_class = getattr(module, payload_class_name)
    except ModuleNotFoundError:
        headers_class, payload_class = None, None

    if headers_class and payload_class:
        return '', headers_class, payload_class

    if not extra_dir:
        if os.path.isdir('/etc/sylk-pushserver'):
            extra_dir = '/etc/sylk-pushserver/applications'
        else:
            current_dir = os.getcwd()
            extra_dir = current_dir + "/config/applications"

    if os.path.isdir(extra_dir):
        sys.path.append(extra_dir)

    error = ''

    try:
        module = importlib.import_module(name.lower())
        try:
            headers_class_name = f'{platform.capitalize()}{name.lower().capitalize()}Headers'
            headers_class = getattr(module, headers_class_name)
            try:
                payload_class_name = f'{platform.capitalize()}{name.lower().capitalize()}Payload'
                payload_class = getattr(module, payload_class_name)
            except AttributeError:
                error = f'{platform.capitalize()}{name.lower().capitalize()}Payload class not found ' \
                        f'in {name.lower()}'
                headers_class, payload_class = None, None
        except AttributeError:
            error = f'{platform.capitalize()}{name.lower().capitalize()}Headers class not found ' \
                    f'in {name.lower()}'
            headers_class, payload_class = None, None
    except ModuleNotFoundError:
        error = f'{name.lower()} module not found'
        headers_class, payload_class = None, None

    return error, headers_class, payload_class


def check_pns_classes(platform: str, extra_dir: str) -> tuple:
    """
    Check for custom classes
    :param name: `str` name of custom app, which corresponds to module
    :param platform: `str` 'apple' or 'firebase'
    :param extra_dir: `str` path to extra applications dir
    :return: a tuple with, error (str), headers_class (class), payload_class (class)
    """

    # Check for known apps:
    try:
        register_module = importlib.import_module(f'pushserver.pns.{platform}')
        register_class = getattr(register_module, f'{platform.capitalize()}Register')
        pns_class = getattr(register_module, f'{platform.capitalize()}PNS')
    except ModuleNotFoundError:
        register_class = None

    if register_class:
        return '', register_class

    if not extra_dir:
        if os.path.isdir('/etc/sylk-pushserver'):
            extra_dir = '/etc/sylk-pushserver/pns'
        else:
            current_dir = os.getcwd()
            extra_dir = current_dir + "/config/pns"

    if os.path.isdir(extra_dir):
        sys.path.append(extra_dir)

    error = ''

    try:
        register_module = importlib.import_module(platform.lower())
        try:
            register_class = getattr(register_module, f'{platform.capitalize()}Register')
            pns_class = getattr(register_module, f'{platform.capitalize()}PNS')
        except AttributeError:
            error = f'{platform.capitalize()}PNS class not found ' \
                    f'in {platform.lower()}'
            register_class = None
    except ModuleNotFoundError:
        error = f'{platform.lower()} module not found in pushserver/pns or {extra_dir}'
        register_class = None

    return error, register_class


def get_pns_from_config(config_path: str, credentials: str, apps_extra_dir: str,
                        pns_extra_dir: str, loggers: dict) -> dict:
    """
    Create a dictionary with applications with their own PN server address, certificates and keys
    :param config_path: `str` path to config file (see config.ini.example)
    :param credentials: `str` path to credentials dir
    :param apps_extra_dir: `str` path to extra applications dir
    :param pns_extra_dir: `str` path to extra pns dir
    :param loggers: `dict` global logging instances to write messages (params.loggers)
    """
    config = configparser.ConfigParser()
    config.read(config_path)
    # pns_dict = {(<app_id>, 'apple')): {'id': str,
    #                                    'name': str,
    #                                    'headers_class': headers_class,
    #                                    'payload_class': payload_class,
    #                                    'pns': ApplePNS,
    #                                    'conn': AppleConn}
    #             (<app_id>, 'firebase'): {'id': str,
    #                                     'name': str,
    #                                    'headers_class': headers_class,
    #                                    'payload_class': payload_class,
    #                                     'pns': FirebasePNS}
    #             (<app_id> ...
    #            }

    pns_register = {}
    invalid_apps = {}
    for id in config.sections():
        app_id = config[id]['app_id']
        name = config[id]['app_type'].lower()
        platform = config[id]['app_platform'].lower()
        voip = config[id].get('voip')
        error, log, log_urls, log_key, log_timeout = '', False, '', '', None
        try:
            log_urls_str = config[id]['log_remote_urls']
            log_urls = set(log_urls_str.split(','))
            log_key = config[id].get('log_key')
            log_timeout = config[id].get('log_time_out')
            log_timeout = int(log_timeout) if log_timeout else None
        except KeyError:
            log = False
        except SyntaxError:
            error = f'log_remote_urls = {log_urls_str} - bad syntax'
            log = False
        log_remote = {'error': error,
                      'log_urls': log_urls,
                      'log_remote_key': log_key,
                      'log_remote_timeout': log_timeout}

        if voip:
            voip = True if voip.lower() == 'true' else False

        error, register_class = check_pns_classes(platform=platform, extra_dir=pns_extra_dir)

        if error:
            reason = error
            invalid_apps[(app_id, platform)] = {'name': name, 'reason': reason}
            continue

        register = register_class(app_id=app_id,
                                  app_name=name,
                                  voip=voip,
                                  config_dict=config[id],
                                  credentials_path=credentials,
                                  loggers=loggers)
        register_entries = register.register_entries
        error = register.error

        if error:
            reason = error
            invalid_apps[(app_id, platform)] = {'name': name, 'reason': reason}
            continue

        error, \
        headers_class, \
        payload_class = check_apps_classes(name,
                                           platform,
                                           apps_extra_dir)

        if error:
            reason = error
            invalid_apps[(app_id, platform)] = {'name': name,
                                                'reason': reason}
            continue

        pns_register[(app_id, platform)] = {'id': id,
                                            'name': name,
                                            'headers_class': headers_class,
                                            'payload_class': payload_class,
                                            'log_remote': log_remote}

        for k, v in register_entries.items():
            pns_register[(app_id, platform)][k] = v

    pnses = []
    for app in pns_register.keys():
        pnses.append(pns_register[app]['pns'].__class__.__name__)
    pnses = set(pnses)

    return {'pns_register': pns_register,
            'invalid_apps': invalid_apps,
            'pnses': pnses}
