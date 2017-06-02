"""
TODO: Replaces lta.py
"""
import json
import urllib
import traceback
import datetime

import requests
import memcache

from api.domain import sensor
from api.providers.configuration.configuration_provider import (
    ConfigurationProvider)
from api.system.logger import ilogger as logger


# TODO: need to profile how much data we are caching
TWO_HOURS = 7200  # seconds
MD_KEY_FMT = '({sensor},{date},{path},{row})'  # use comma because date has dash
cache = memcache.Client(['127.0.0.1:11211'], debug=0)
config = ConfigurationProvider()

if config.mode in ('dev', 'tst'):
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('requests.packages').setLevel(logging.DEBUG)


class LTAError(Exception):
    def __init__(self, message):
        logging.error('ERR {}'.format(message))
        super(LTAError, self).__init__(message)


# -----------------------------------------------------------------------------+
# Find Documentation here:                                                     |
#      https://earthexplorer.usgs.gov/inventory/documentation/json-api         |
class LTAService(object):
    def __init__(self):
        self.base_url = config.url_for('earthexplorer.json')
        mode = config.mode
        self.api_version = config.get('bulk.{0}.json.version'.format(mode))
        self.agent = config.get('bulk.{0}.json.username'.format(mode))
        self.agent_wurd = config.get('bulk.{0}.json.password'.format(mode))
        self.current_user = None
        self.token = None
        self.node = 'EE'  # EarthExplorer

    def __del__(self):
        if self.current_user:
            self.logout()
            self.token = None
            self.current_user = None

    @property
    def base_url(self):
        return self._base_url

    @base_url.setter
    def base_url(self, value):
        if not isinstance(value, basestring):
            raise TypeError('LTAService base_url must be string')
        self._base_url = value

    @staticmethod
    def _parse(response):
        """
        Attempt to parse the JSON response, which always contains additional
        information that we might not always want to look at (except on error)

        :param response: requests.models.Response
        :return: dict
        """
        data = dict()
        try:
            data = response.json()
        except Exception:  # FIXME: be more specific
            msg = ('unable to parse JSON response.\n'
                   'traceback:\n{}'.format(traceback.format_exc()))
            raise LTAError(msg)

        if not response.ok:
            raise LTAError('bad request: {}\nerror:{}'
                           .format(response.status_code, data.get('error')))
        if data.get('error'):
            raise LTAError('error returned: {}'.format(data.get('error')))
        if 'data' not in data:
            raise LTAError('no data found:\n{}'.format(data))

        return data

    def _request(self, endpoint, data=None, verb='post'):
        """
        Wrapper function for debugging connectivity issues

        :param endpoint: the resource location on the host
        :param data: optional message body
        :param verb: HTTP method of GET or POST
        :return:
        """
        url = self.base_url + endpoint
        logger.debug('{verb} {url}:\n{payload}'
                     .format(verb=verb.upper(), url=url, payload=data))
        # FIXME: why is this necessary? ========================================
        request = url + '?jsonRequest={}'.format(urllib.quote(json.dumps(data)))
        response = getattr(requests, verb)(request)
        # ======================================================================
        logger.debug('RESPONSE:{}\n{}'.format(response, response.content))
        return self._parse(response)

    def _get(self, endpoint, data=None):
        return self._request(endpoint, data, verb='get')

    def _post(self, endpoint, data=None):
        return self._request(endpoint, data, verb='post')

    # Formatting wrappers on resource endpoints ================================
    def available(self):
        """
        Checks the LTA API status endpoint and compares an expected API version

        :return: bool
        """
        data = self._get('status')
        if data:
            return self.api_version == data.get('api_version')

    def login(self, username, password):
        """
        Authenticates the user and returns an API Key

        :param username: USGS registration username
        :param password: USGS registration password
        :return: str
        """
        endpoint = 'login'
        payload = dict(username=username, password=password, authType='EROS')
        resp = self._post(endpoint, payload)
        self.token = resp.get('data')
        self.current_user = username

    def logout(self):
        """
        Remove the users API key from being used in the future

        :return: bool
        """
        endpoint = 'logout'
        payload = dict(apiKey=self.token)
        resp = self._get(endpoint, payload)
        if resp.get('data'):
            return True
        else:
            raise LTAError('{} logout failed'.format(self.current_user))

    def fields(self, dataset=''):
        """
        Returns the metadata filter field list for the specified dataset

        :param dataset: Identifies the dataset
        :return: list
        """
        endpoint = 'datasetfields'
        payload = dict(datasetName=dataset, apiKey=self.token, node=self.node)
        resp = self._get(endpoint, payload)
        return resp.get('data')

    def search(self, dataset, mxr=50000, tstart=None, tend=None, filters=None):
        """
        Allows user to search for scenes based on temporal extents, spatial
        extents, and scene metadata

        :param dataset: Identifies the dataset
        :param mxr:  the maximum number of results to return (request limit 50k)
        :param tstart: search the dataset temporally (ISO 8601 Formatted Date)
        :param tend: search the dataset temporally (ISO 8601 Formatted Date)
        :param filters: filter results based on specific metadata fields
        :return: list
        """
        endpoint = 'search'
        payload = dict(datasetName=dataset, maxResults=mxr,
                       apiKey=self.token, node=self.node)
        if tstart:
            payload.update(startDate=tstart)
        if tend:
            payload.update(endDate=tend)
        if filters:
            payload.update(dict(additionalCriteria=filters))

        resp = self._get(endpoint, payload)

        n_results = resp.get('data', dict()).get('totalHits', 0)
        if n_results == max:
            logger.warning('Maximum results {} returned'.format(max))
        else:
            logger.debug('Total Hits: {}'.format(n_results))

        result_list = resp.get('data', dict()).get('results', list())
        return result_list

    def metadata(self, dataset, ids):
        """
        Scene metadata for the search result set

        :param dataset: Identifies the dataset
        :param ids: Identifies multiple scenes
        :return: list
        """
        endpoint = 'metadata'
        payload = dict(datasetName=dataset, apiKey=self.token, node=self.node,
                       entityIds=ids)
        resp = self._get(endpoint, payload)
        return resp.get('data')


class LTAUser(object):
    def __init__(self, username, password):
        self.api = LTAService()
        self.api.login(username, password)
        self.username = self.api.current_user

    def __repr__(self):
        return 'LTAUser: {}'.format(self.__dict__)

    def __getitem__(self, item):
        return self.__dict__.get(item)


class LTAScenes(object):

    def __init__(self, user):
        if not isinstance(user, LTAUser):
            raise LTAError('invalid user object supplied')

        self.user = user

    def __repr__(self):
        return "LTAScenes (as {user})".format(user=self.user['username'])

    def get_filters_for_path_row(self, path, row, dataset=''):
        """
        Create the complex filter needed in order to search for only a given
        path and row. The "fieldId" of Path/Row changes between different
        datasets (e.g. Landsat_8 vs Landsat_7)

        :param path: Desired WRS Path
        :param row: Desired WRS Row
        :param dataset: Name of the dataset
        :return:
        """
        field_list = self.user.api.fields(dataset)
        parser = lambda x, y: x['fieldId'] if x['name'] == y else None
        pid = filter(lambda x: x is not None,
                     map(parser, field_list, ['WRS Path'] * len(field_list)))
        rid = filter(lambda x: x is not None,
                     map(parser, field_list, ['WRS Row'] * len(field_list)))
        filters = dict(filterType='and',
                       childFilters=[dict(filterType='between',
                                          fieldId=pid,
                                          firstValue=path,
                                          secondValue=path),
                                     dict(filterType='between',
                                          fieldId=rid,
                                          firstValue=row,
                                          secondValue=row)])
        return filters

    @staticmethod
    def extract_acq_info(sid):
        """
        Extract the "acquisition info" (sensor/date/location) [the cache key]

        :param sid: Landsat Scene ID
        :return: dict
        """
        sinfo = sensor.instance(sid)
        dt = datetime.datetime.strptime(sinfo.julian, '%Y%j')
        info = dict(sensor=sinfo.lta_json_name, date=dt.strftime('%Y-%m-%d'),
                    path=sinfo.path, row=sinfo.row)
        return info

    def grab_scene_metadata(self, sid):
        """
        Get all metadata for a scene-id, using the cache if already available

        :param sid: Landsat Scene ID
        :return: dict
        """
        api = self.user.api
        info = self.extract_acq_info(sid)
        cache_key = MD_KEY_FMT.format(**info)
        # TODO: should use cache.get_multi(...) to reduce round-trips
        # TODO: should this get cached inside the LTA connection?
        res = cache.get(cache_key)
        if res is None:
            filters = self.get_filters_for_path_row(info['path'], info['row'],
                                                    info['sensor'])
            res = api.search(info['sensor'], tstart=info['date'],
                             tend=info['date'], filters=filters)
            if isinstance(res, list) and len(res) > 0:
                logger.debug('cache key: {}'.format(cache_key))
                cache.set(cache_key, res, TWO_HOURS)
        return res

    def verify_scenes(self, id_list):
        search_res = dict()
        for sid in id_list:
            res = self.grab_scene_metadata(sid)
            search_res[sid] = len(res) == 1
        return search_res

    def get_download_urls(self, id_list):
        search_res = dict()
        for sid in id_list:
            res = self.grab_scene_metadata(sid)
            search_res[sid] = res[-1].get('dataAccessUrl')
        return search_res


''' This is the public interface that calling code should use to interact
    with this module'''


def get_session():
    return LTAService().login()


def available():
    return LTAService().available()
