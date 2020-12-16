import os
import sys

from application.configuration import ConfigSection, ConfigSetting
from application.configuration.datatypes import HostnameList
from application.python.descriptor import classproperty


__all__ = 'CassandraConfig', 'ServerConfig'


class Path(str):
    def __new__(cls, path):
        if path:
            path = os.path.normpath(path)
        return str.__new__(cls, path)

    @property
    def normalized(self):
        return os.path.expanduser(self)


class VarResources(object):
    """Provide access to Sylk-Pushserver's resources that should go in /var"""

    _cached_directory = None

    @classproperty
    def directory(cls):
        if cls._cached_directory is None:
            binary_directory = os.path.dirname(os.path.realpath(sys.argv[0]))
            if os.path.basename(binary_directory) == 'bin':
                path = '/var'
            else:
                path = 'var'
            cls._cached_directory = os.path.abspath(path)
        return cls._cached_directory

    @classmethod
    def get(cls, resource):
        return os.path.join(cls.directory, resource or u'')


class CassandraConfig(ConfigSection):
    __cfgfile__ = 'general.ini'
    __section__ = 'Cassandra'

    cluster_contact_points = ConfigSetting(type=HostnameList, value=None)
    keyspace = ConfigSetting(type=str, value='')
    table = ConfigSetting(type=str, value='')
    debug = False

class ServerConfig(ConfigSection):
    __cfgfile__ = 'general.ini'
    __section__ = 'server'

    spool_dir = ConfigSetting(type=Path, value=Path(VarResources.get('spool/sylk-pushserver')))
