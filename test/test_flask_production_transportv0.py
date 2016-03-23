#!/usr/bin/env python

import base64
import json
import unittest

from api.interfaces.ordering.mocks.version0 import MockAPI
from api.providers.production.mocks.production_provider import MockProductionProvider
from api.transports import http
from api.providers.configuration.configuration_provider import ConfigurationProvider
from mock import patch

api = MockAPI()
production_provider = MockProductionProvider()

class ProductionTransportTestCase(unittest.TestCase):

    def setUp(self):
        cfg = ConfigurationProvider()

        self.app = http.app.test_client()
        self.app.testing = True

        token = '{}:{}'.format(cfg.devuser, cfg.devword)
        auth_string = "Basic {}".format(base64.b64encode(token))
        self.headers = {"Authorization": auth_string}

        self.useremail = cfg.devmail


    def tearDown(self):
        pass

    def test_get_production_api(self):
        response = self.app.get('/production-api', headers=self.headers)
        response_data = json.loads(response.get_data())
        assert response.content_type == 'application/json'
        assert response_data.keys() == ['versions']
        assert response_data['versions'].keys() == ["0"]

    def test_get_production_api_v0(self):
        response = self.app.get('/production-api/v0', headers=self.headers)
        response_data = json.loads(response.get_data())
        assert response_data.keys() == ["0"]
        assert response_data['0'].keys() == ["operations", "description"]
        assert "ESPA Production" in response_data['0']['description']

    @patch('api.providers.production.production_provider.ProductionProvider.get_products_to_process',
            production_provider.get_products_to_process_inputs)
    def test_get_production_api_products_modis(self):
        url = "/production-api/v0/products?for_user=bilbo&product_types=modis"
        response = self.app.get(url, headers=self.headers)
        response_data = json.loads(response.get_data())
        correct_resp = {'encode_urls': False, 'for_user': 'bilbo',
                        'record_limit': 500, 'product_types': 'modis',
                        'priority': None}
        assert response_data == correct_resp

    @patch('api.providers.production.production_provider.ProductionProvider.get_products_to_process',
            production_provider.get_products_to_process_inputs)
    def test_get_production_api_products_landsat(self):
        url = "/production-api/v0/products?for_user=bilbo&product_types=landsat"
        response = self.app.get(url, headers=self.headers)
        response_data = json.loads(response.get_data())
        correct_resp = {'encode_urls': False, 'for_user': 'bilbo',
                        'record_limit': 500, 'product_types': 'landsat',
                        'priority': None}
        assert response_data == correct_resp

    @patch('api.providers.production.production_provider.ProductionProvider.update_status',
            production_provider.update_status_inputs)
    def test_post_production_api_update_status(self):
        url = "/production-api/v0/update_status"
        data_dict = {'name': 't10000xyz401', 'orderid': 'kyle@usgs.gov-09222015-123456',
                    'processing_loc': 'update_status', 'status': 'updated'}
        response = self.app.post(url, data=json.dumps(data_dict), headers=self.headers)
        response_data = json.loads(response.get_data())
        assert response_data == data_dict

    @patch('api.providers.production.production_provider.ProductionProvider.set_product_error',
            production_provider.set_product_error_inputs)
    def test_post_production_api_set_product_error(self):
        url = "/production-api/v0/set_product_error"
        data_dict = {'name': 't10000xyz401', 'orderid': 'kyle@usgs.gov-09222015-123456',
                     'processing_loc': 'xyz', 'error': 'oopsie'}
        response = self.app.post(url, data=json.dumps(data_dict), headers=self.headers)
        response_data = json.loads(response.get_data())
        assert response_data == data_dict

    @patch('api.providers.production.production_provider.ProductionProvider.set_product_unavailable',
            production_provider.set_product_unavailable_inputs)
    def test_post_production_api_set_product_unavailable(self):
        url = "/production-api/v0/set_product_unavailable"
        data_dict = {'name': 't10000xyz401', 'orderid': 'kyle@usgs.gov-09222015-123456',
                     'processing_loc': 'xyz', 'error': 'oopsie', 'note': 'them notes'}
        response = self.app.post(url, data=json.dumps(data_dict), headers=self.headers)
        response_data = json.loads(response.get_data())
        assert response_data == data_dict

    @patch('api.providers.production.production_provider.ProductionProvider.mark_product_complete',
            production_provider.set_mark_product_complete_inputs)
    def test_post_production_api_mark_product_complete(self):
        url = "/production-api/v0/mark_product_complete"
        data_dict = {'name': 't10000xyz401', 'orderid': 'kyle@usgs.gov-09222015-123456',
                     'processing_loc': 'xyz',
                     'completed_file_location': '/tmp',
                     'cksum_file_location': '/tmp/txt.txt',
                     'log_file_contents': 'details'}
        response = self.app.post(url, data=json.dumps(data_dict), headers=self.headers)
        response_data = json.loads(response.get_data())
        assert response_data == data_dict

    @patch('api.providers.production.production_provider.ProductionProvider.handle_orders',
            production_provider.respond_true)
    def test_post_production_api_handle_orders(self):
        url = "/production-api/v0/handle-orders"
        response = self.app.post(url, data=json.dumps({}), headers=self.headers)
        response_data = json.loads(response.get_data())
        assert response_data is True

    @patch('api.providers.production.production_provider.ProductionProvider.queue_products',
            production_provider.queue_products_inputs)
    def test_post_production_api_queue_products(self):
        url = "/production-api/v0/queue-products"
        data_dict = {'order_name_tuple_list': 'order_name_tuple_list',
                     'processing_location': 'processing_location',
                     'job_name': 'job_name'}
        response = self.app.post(url, data=json.dumps(data_dict), headers=self.headers)
        response_data = json.loads(response.get_data())
        assert response_data == data_dict

    def test_get_production_api_configurations(self):
        url = "/production-api/v0/configuration/system_message_title"
        response = self.app.get(url, headers=self.headers)
        response_data = json.loads(response.get_data())
        assert response_data.keys() == ['system_message_title']
