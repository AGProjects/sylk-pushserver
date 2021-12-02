import os
import _pickle as pickle

import logging

from application.python.types import Singleton
from application.system import makedirs

from collections import defaultdict

from pushserver.resources import settings
from pushserver.resources.utils import log_event

from .configuration import CassandraConfig, ServerConfig
from .errors import StorageError


__all__ = 'TokenStorage'


CASSANDRA_MODULES_AVAILABLE = False
try:
    from cassandra.cqlengine import columns, connection
except ImportError:
    pass
else:
    try:
        from cassandra.cqlengine.models import Model
    except ImportError:
        pass
    else:
        CASSANDRA_MODULES_AVAILABLE = True
        from cassandra import InvalidRequest
        from cassandra.cqlengine import CQLEngineException
        from cassandra.cqlengine.query import LWTException
        from cassandra.cluster import NoHostAvailable
        from cassandra.io import asyncioreactor
        from cassandra.policies import DCAwareRoundRobinPolicy
        from pushserver.models.cassandra import PushTokens, OpenSips
        if CassandraConfig.table:
            PushTokens.__table_name__ = CassandraConfig.table


class FileStorage(object):
    def __init__(self):
        self._tokens = defaultdict()

    def _save(self):
        with open(os.path.join(ServerConfig.spool_dir.normalized, 'webrtc_device_tokens'), 'wb+') as f:
            pickle.dump(self._tokens, f)

    def load(self):
        try:
            tokens = pickle.load(open(os.path.join(ServerConfig.spool_dir, 'webrtc_device_tokens'), 'rb'))
        except Exception:
            pass
        else:
            self._tokens.update(tokens)

    def __getitem__(self, key):
        try:
            return self._tokens[key]
        except KeyError:
            return {}

    def add(self, account, contact_params):
        try:
            (token, background_token) = contact_params.token.split('#')
        except ValueError:
            token = contact_params.token
            background_token = None

        data = contact_params.__dict__
        data['token'] = token
        data['background_token'] = background_token

        key = f'{contact_params.app_id}-{contact_params.device_id}'
        if account in self._tokens:
            self._tokens[account][key] = data
        else:
            self._tokens[account] = {key: data}
        self._save()

    def remove(self, account, app_id, device_id):
        key = f'{app_id}-{device_id}'
        try:
            del self._tokens[account][key]
        except KeyError:
            pass
        self._save()


class CassandraStorage(object):
    def load(self):
        try:
            connection.setup(CassandraConfig.cluster_contact_points, CassandraConfig.keyspace, load_balancing_policy=DCAwareRoundRobinPolicy(), protocol_version=4, connection_class=asyncioreactor.AsyncioConnection)
        except NoHostAvailable:
            msg='Not able to connect to any of the Cassandra contact points'
            log_event(loggers=settings.params.loggers, msg=msg, level='error')

    def __getitem__(self, key):
        def query_tokens(key):
            username, domain = key.split('@', 1)
            tokens = {}
            try:
                for device in PushTokens.objects(PushTokens.username == username, PushTokens.domain == domain):
                    tokens[f'{device.app_id}-{device.device_id}'] = {'device_id': device.device_id, 'token': device.device_token,
                                                                     'background_token': device.background_token, 'platform': device.platform,
                                                                     'app_id': device.app_id, 'silent': bool(int(device.silent))}
            except CQLEngineException as e:
                log_event(loggers=settings.params.loggers, msg=f'Get token(s) failed: {e}', level='error')
                raise StorageError
            return tokens
        return query_tokens(key)

    def add(self, account, contact_params):
        username, domain = account.split('@', 1)

        token = contact_params.token
        background_token = None
        if contact_params.platform == 'apple':
            try:
                (token, background_token) = contact_params.token.split('-')
            except ValueError:
                pass

        try:
            PushTokens.create(username=username, domain=domain, device_id=contact_params.device_id,
                              device_token=token, background_token=background_token, platform=contact_params.platform,
                              silent=str(int(contact_params.silent is True)), app_id=contact_params.app_id,
                              user_agent=contact_params.user_agent)
        except (CQLEngineException, InvalidRequest) as e:
            log_event(loggers=settings.params.loggers, msg=f'Storing token failed: {e}', level='error')
            raise StorageError
        try:
            OpenSips.create(opensipskey=account, opensipsval='1')
        except (CQLEngineException, InvalidRequest) as e:
            log_event(loggers=settings.params.loggers, msg=e, level='error')
            raise StorageError

    def remove(self, account, app_id, device_id):
        username, domain = account.split('@', 1)
        try:
            PushTokens.objects(PushTokens.username == username, PushTokens.domain == domain, PushTokens.device_id == device_id, PushTokens.app_id == app_id).if_exists().delete()
        except LWTException:
            pass
        else:
            # We need to check for other device_ids/app_ids before we can remove the cache value for OpenSIPS
            if not self[account]:
                try:
                    OpenSips.objects(OpenSips.opensipskey == account).if_exists().delete()
                except LWTException:
                    pass

class TokenStorage(object, metaclass=Singleton):

    def __new__(self):
        configuration = CassandraConfig.__cfgtype__(CassandraConfig.__cfgfile__)
        if configuration.files:
            msg='Reading storage configuration from {}'.format(', '.join(configuration.files))
            log_event(loggers=settings.params.loggers, msg=msg, level='info')
        makedirs(ServerConfig.spool_dir.normalized)
        if CASSANDRA_MODULES_AVAILABLE and CassandraConfig.cluster_contact_points:
            if CassandraConfig.debug:
                logging.getLogger('cassandra').setLevel(logging.DEBUG)
            else:
                logging.getLogger('cassandra').setLevel(logging.INFO)
            log_event(loggers=settings.params.loggers, msg='Using Cassandra for token storage', level='info')
            return CassandraStorage()
        else:
            log_event(loggers=settings.params.loggers, msg='Using pickle file for token storage', level='info')
            return FileStorage()
