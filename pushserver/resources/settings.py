import configparser
import logging
import os
from ipaddress import ip_network
from pushserver.pns.register import get_pns_from_config


try:
    from systemd.journal import JournaldLogHandler
except ImportError:
    from systemd.journal import JournalHandler


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

        self.default_dir = '/etc/sylk-pushserver'
        self.current_dir = os.getcwd()
        self.default_host, self.default_port = '127.0.0.1', '8400'

        self.config_dir = config_dir
        self.debug = debug
        self.ip, self.port = ip, port

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
        look for general.ini in /etc/sylk-pushserver or ./config
        if general.ini is not there, server will start with default settings
        """
        dir, error = {}, ''

        config_dir = self.config_dir

        if not config_dir:
            error = f'{self.config_dir} no such directory, ' \
                    f'server will run with default settings.'
            if os.path.exists(f'{self.default_dir}/general.ini'):
                config_dir = self.default_dir
            elif os.path.exists(f'{self.current_dir}/config/general.ini'):
                config_dir = self.current_dir
            else:
                error = f'general.ini cofig files not found in ' \
                        f'{self.default_dir} ' \
                        f'or {self.current_dir}/config,' \
                        f'server will run with default settings.'

        dir['path'], dir['error'] = config_dir, error
        return dir

    def set_file(self):

        file, path, error = {}, '', ''
        if not self.dir.get('error'):
            path = f"{self.dir['path']}/general.ini"
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
        apps_path, apps_cred, apps_extra_dir, pns_extra_dir = '', '', '', ''
        apps_settings = False

        if not self.dir['error']:
            if self.file['path']:
                config = configparser.ConfigParser()
                config.read(self.file['path'])
                try:
                    apps_path = f"{config['applications']['config_file']}"
                    apps_cred = f"{config['applications'].get('credentials_folder')}"
                    apps_extra_dir = f"{config['applications'].get('extra_applications_dir')}"
                    pns_extra_dir = f"{config['applications'].get('extra_pns_dir')}"
                    paths_list = [apps_path, apps_cred, apps_extra_dir, pns_extra_dir]

                    for i, path in enumerate(paths_list):
                        if not path.startswith('/'):
                            paths_list[i] = f'{self.config_dir}/{path}'

                    apps_path = paths_list[0]
                    apps_cred = paths_list[1]
                    apps_extra_dir = paths_list[2]
                    pns_extra_dir = paths_list[3]

                    apps_path_exists = os.path.exists(apps_path)
                    cred_path_exists = os.path.exists(apps_cred)
                    extra_apps_dir_exists = os.path.exists(apps_extra_dir)
                    extra_pns_dir_exists = os.path.exists(pns_extra_dir)

                    if not apps_path_exists:
                        self.dir['error'] = f" Can not start: " \
                                            f"applications.ini config file not found in " \
                                            f"{apps_path}"
                        apps_path, apps_cred, apps_extra_dir, pns_extra_dir = '', '', '', ''
                    if not cred_path_exists:
                        self.dir['error'] = f" Can not start: " \
                                            f"{apps_cred} no such directory"
                        apps_path, apps_cred, apps_extra_dir , pns_extra_dir = '', '', '', ''
                    if apps_path_exists and cred_path_exists:
                        apps_settings = True

                except KeyError:
                    apps_path, apps_cred, apps_extra_dir = '', '', ''

            elif os.path.exists(self.default_dir):
                if os.path.exists(f'{self.default_dir}/applications.ini'):
                    apps_path = f'{self.default_dir}/applications.ini'
                    apps_cred = f'{self.default_dir}/credentials'
                    apps_extra_dir = f'{self.default_dir}/applications'
                    pns_extra_dir = f'{self.default_dir}/pns'
                    apps_settings = True

        if not apps_settings:
            if os.path.exists(self.default_dir):
                if os.path.exists(f'{self.default_dir}/applications.ini'):
                    apps_path = f'{self.default_dir}/applications.ini'
                    apps_cred = f'{self.default_dir}/credentials'
                    apps_extra_dir = f'{self.default_dir}/applications'
                    pns_extra_dir = f'{self.default_dir}/pns'
                    apps_settings = True

        if apps_path:
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

        if not apps_settings:
            self.dir['error'] = f'Can not start: ' \
                                f'applications.ini config file not found'

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
                log_path = f"{config['server']['log_file']}"
                try:
                    str_debug = config['server']['debug'].lower()
                except KeyError:
                    str_debug = False
                debug = True if str_debug == 'true' else False
                debug = debug or self.debug
            except KeyError:
                log_path, debug = default_path, False

        logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

        formatter = logging.Formatter('[%(levelname)s] %(message)s')

        # log to file
        if log_path:
            logger_file = logging.getLogger('to_file')
            logger_file.setLevel(logging.DEBUG)
            try:
                loggers['to_file'] = logger_file
                hdlr = logging.FileHandler(log_path)
                hdlr.setFormatter(formatter)
                logger_file.addHandler(hdlr)
            except PermissionError:
                self.dir['error'] = f'Permission denied: {log_path}, ' \
                                    f'debug log file requires ' \
                                    f'run sylk-pushserver with sudo.'
        # log to journal
        logger_journal = logging.getLogger('to_journal')
        logger_journal.setLevel(logging.DEBUG)

        loggers['to_journal'] = logger_journal

        try:
            journal_handler = JournaldLogHandler()
        except NameError:
            journal_handler = JournalHandler()

        journal_handler.setFormatter(formatter)
        logger_journal.addHandler(journal_handler)

        debug = debug or self.debug
        loggers['debug'] = debug

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