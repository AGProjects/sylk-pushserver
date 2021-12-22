import configparser
import logging
import os
from ipaddress import ip_network
from pushserver.pns.register import get_pns_from_config
from application import log


class ConfigParams(object):
    """
    Settings params to share across modules.

    :param dir: `dict` with 'path' to config dir an 'error' if exists
    :param file: `dict` with 'path' to config file
    :param server: `dict` with host, port and tls_cert from config file
    :param apps: `dict` with path, credentials and extra_dir from config file
    :param loggers: `dict` global logging instances to write messages (params.loggers)
    :param allowed_pool: `list` of allowed hosts for requests

    if there is any error with config dir or config file,
    others params will be setted to None.
    """

    def __init__(self, config_dir, debug, ip, port):

        self.default_host, self.default_port = '127.0.0.1', '8400'

        self.config_dir = config_dir
        self.debug = debug
        self.ip, self.port = ip, port

        self.cfg_file = f'general.ini'
        self.dir = self.set_dir()
        self.file = self.set_file()
        self.loggers = self.set_loggers()
        self.apps = self.set_apps()
        self.register = self.set_register()
        self.allowed_pool = self.set_allowed_pool()
        self.return_async = self.set_return_async()

    def set_dir(self):
        """
        if config directory was not specified from command line
        look for general.ini in /etc/sylk-pushserver
        if general.ini is not there, server will start with default settings
        """
        dir, error = {}, ''

        config_dir = self.config_dir

        msg = f"Reading configuration from {config_dir}"
        log.info(msg)

        if not os.path.exists(f'{self.config_dir}/{self.cfg_file}'):
            config_dir = ''
            error = f'No {self.cfg_file} found in {self.config_dir}, ' \
                    f'server will run with default settings.'

        dir['path'], dir['error'] = config_dir, error
        return dir

    def set_file(self):

        file, path, error = {}, '', ''
        if not self.dir.get('error'):
            path = f"{self.dir['path']}/{self.cfg_file}"
            error = ''
        elif 'default' in self.dir.get('error'):
            path = ''
            error = self.dir.get('error')

        file['path'], file['error'] = path, error
        return file

    @property
    def server(self):
        server = {}

        if not self.file.get('error') or 'default' in self.file.get('error'):
            config = configparser.ConfigParser()
            config.read(self.file['path'])
            try:
                server_settings = config['server']
            except KeyError:
                server_settings = {}
            if self.ip:
                server['host'] = self.ip
            else:
                server['host'] = server_settings.get('host') or self.default_host
            if self.port:
                server['port'] = self.port
            else:
                server['port'] = server_settings.get('port') or self.default_port

            server['tls_cert'] = server_settings.get('tls_certificate') or ''
        return server

    def set_apps(self):

        apps = {}
        apps_path = f'{self.config_dir}/applications.ini'
        apps_cred = f'{self.config_dir}/credentials'
        apps_extra_dir = f'{self.config_dir}/applications'
        pns_extra_dir = f'{self.config_dir}/pns'

        if self.file['path']:
            logging.info(f"Reading: {self.file['path']}")
            config = configparser.ConfigParser()
            config.read(self.file['path'])

            config_apps_path = f"{config['applications'].get('config_file')}"
            config_apps_cred = f"{config['applications'].get('credentials_folder')}"
            config_apps_extra_dir = f"{config['applications'].get('extra_applications_dir')}"
            config_pns_extra_dir = f"{config['applications'].get('extra_pns_dir')}"
            paths_list = [config_apps_path, config_apps_cred, config_apps_extra_dir, config_pns_extra_dir]

            for i, path in enumerate(paths_list):
                if not path.startswith('/'):
                    paths_list[i] = f'{self.config_dir}/{path}'

            config_apps_path = paths_list[0]
            config_apps_cred = paths_list[1]
            config_apps_extra_dir = paths_list[2]
            config_pns_extra_dir = paths_list[3]

            apps_path_exists = os.path.exists(config_apps_path)
            cred_path_exists = os.path.exists(config_apps_cred)
            extra_apps_dir_exists = os.path.exists(config_apps_extra_dir)
            extra_pns_dir_exists = os.path.exists(config_pns_extra_dir)

            if apps_path_exists:
                apps_path = config_apps_path
            if cred_path_exists:
                apps_cred = config_apps_cred
            if extra_apps_dir_exists:
                apps_extra_dir = config_apps_extra_dir
            if extra_pns_dir_exists:
                pns_extra_dir = config_pns_extra_dir
        else:
            logging.info(self.dir['error'])

        if not os.path.exists(apps_path):
            self.dir['error'] = f'Required config file not found: {apps_path}'
            apps_path, apps_cred, apps_extra_dir = '', '', ''
        else:
            logging.info(f'Reading: {apps_path}')
            config = configparser.ConfigParser()
            config.read(apps_path)
            if config.sections():
                for id in config.sections():
                    try:
                        config[id]['app_id']
                        config[id]['app_type']
                        config[id]['app_platform'].lower()
                    except KeyError:
                        self.dir['error'] = f'Can not start: ' \
                                            f'{apps_path} config file has not ' \
                                            f'valid application settings'
                        apps_path, apps_cred, apps_extra_dir = '', '', ''

        apps['path'] = apps_path
        apps['credentials'] = apps_cred
        apps['apps_extra_dir'] = apps_extra_dir
        apps['pns_extra_dir'] = pns_extra_dir
        return apps

    def set_loggers(self):

        debug = self.debug if self.debug else False
        loggers = {}
        config = configparser.ConfigParser()
        default_path = '/var/log/sylk-pushserver/push.log'
        log_path = ''

        if not self.file['error']:
            config.read(self.file['path'])

            try:
                log_to_file = f"{config['server']['log_to_file']}"
                log_to_file = True if log_to_file.lower() == 'true' else False
            except KeyError:
                pass
            else:
                if log_to_file:
                    try:
                        log_path = f"{config['server']['log_file']}"
                    except KeyError:
                        log_path = default_path

            try:
                str_debug = config['server']['debug'].lower()
            except KeyError:
                str_debug = False
            debug = True if str_debug == 'true' else False
            debug = debug or self.debug

        formatter = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        logger_journal = logging.getLogger()

        loggers['to_journal'] = logger_journal

        if log_path:
            try:
                hdlr = logging.FileHandler(log_path)
                hdlr.setFormatter(formatter)
                hdlr.setLevel(logging.DEBUG)
                logger_journal.addHandler(hdlr)
            except PermissionError:
                log.warning(f'Permission denied for log file: {log_path}, ' \
                            f'logging will only be in the journal or foreground')

        debug = debug or self.debug
        loggers['debug'] = debug
        if debug:
            logger_journal.setLevel(logging.DEBUG)

        debug_hpack = False
        try:
            debug_hpack = True if f"{config['server']['debug_hpack']}".lower() == 'true' else False
        except KeyError:
            pass

        if not debug_hpack:
            logging.getLogger("hpack").setLevel(logging.INFO)

        return loggers

    def set_register(self):
        if not self.dir['error'] or 'default' in self.dir['error']:
            apps_path, apps_cred = self.apps['path'], self.apps['credentials']
            apps_extra_dir = self.apps['apps_extra_dir']
            pns_extra_dir = self.apps['pns_extra_dir']
            return get_pns_from_config(config_path=apps_path,
                                       credentials=apps_cred,
                                       apps_extra_dir=apps_extra_dir,
                                       pns_extra_dir=pns_extra_dir,
                                       loggers=self.loggers)

    @property
    def pns_register(self):
        return self.register['pns_register']

    @property
    def invalid_apps(self):
        return self.register['invalid_apps']

    @property
    def pnses(self):
        return self.register['pnses']

    def set_allowed_pool(self):
        if self.dir['error']:
            return None

        if not self.file['path']:
            return None

        allowed_pool = []
        allowed_hosts_str = ''
        config = configparser.ConfigParser()
        config.read(self.file['path'])
        try:
            allowed_hosts_str = config['server']['allowed_hosts']
            allowed_hosts = allowed_hosts_str.split(', ')
        except KeyError:
            return allowed_pool
        except SyntaxError:
            error = f'allowed_hosts = {allowed_hosts_str} - bad syntax'
            self.dir['error'] = error
            return allowed_pool

        if type(allowed_hosts) not in (list, tuple):
            error = f'allowed_hosts = {allowed_hosts} - bad syntax'
            self.dir['error'] = error
            return allowed_pool

        config.read(self.file['path'])
        for addr in allowed_hosts:
            try:
                net = f'{addr}/32' if '/' not in addr else addr
                allowed_pool.append(ip_network(net))
            except ValueError as e:
                error = f'wrong acl settings: {e}'
                self.dir['error'] = error
                return []

        return set(allowed_pool)

    def set_return_async(self):
        return_async = True
        config = configparser.ConfigParser()

        if not self.file['error']:
            config.read(self.file['path'])
            try:
                return_async = config['server']['return_async']
                return_async = True if return_async.lower() == 'true' else False

            except KeyError:
                return_async = True

        return return_async


def init(config_dir, debug, ip, port):
    global params
    params = ConfigParams(config_dir, debug, ip, port)
    return params


def update_params(config_dir, debug, ip, port):
    global params
    try:
        params = ConfigParams(config_dir, debug, ip, port)
    except Exception as ex:
        print(f'Settings can not be updated, reason: {ex}')
    return params
