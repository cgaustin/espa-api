"""
Purpose: serve up settings stored
on the configuration table
"""

from api.util import api_cfg
from api.util.dbconnect import DBConnect
import os

class ApiConfigException(Exception):
    pass

class ApiConfig(object):
    """
    Object for serving up settings
    stored in the database
    """

    def __init__(self, cfgfile=None):

        cfgout = {}

        if cfgfile is None:
            cfg = api_cfg('db')
        else:
            cfg = api_cfg('db', cfgfile)

        with DBConnect(**cfg) as db:
            con_query = "select key, value from ordering_configuration;"
            db.select(con_query)
            for i in db:
                cfgout[i['key']] = i['value']

        self.cfg = api_cfg() 
        self.settings = cfgout

    @property
    def mode(self):
        apimode = 'dev'

        if 'ESPA_ENV' in os.environ.keys():
            apimode = os.environ['ESPA_ENV']

        if apimode not in ['dev', 'tst', 'ops']:
            raise ApiConfigException('Invalid environment value for ESPA_ENV: {0}'.format(apimode))

        return apimode

    def url_for(self, service_name):
        key = "url.{0}.{1}".format(self.mode, service_name)
        return self.settings[key]

