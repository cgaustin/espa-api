#!/usr/bin/env python
import os
import unittest
import datetime
from mock import patch
from api.external.mocks import lta, lpdaac

from api.domain.mocks.order import MockOrder
from api.domain.mocks.user import MockUser
from api.system.mocks import errors
from api.domain.user import User
from api.domain.order import Order
from api.domain.scene import Scene
from api.interfaces.ordering.version0 import API
from api.notification import emails
from api.providers.ordering.mocks.production_provider import MockProductionProvider

from api.providers.ordering.production_provider import ProductionProvider

api = API()
production_provider = ProductionProvider()
mock_production_provider = MockProductionProvider()

class TestProductionAPI(unittest.TestCase):
    def setUp(self):
        os.environ['espa_api_testing'] = 'True'
        # create a user
        self.mock_user = MockUser()
        self.mock_order = MockOrder()
        self.user_id = self.mock_user.add_testing_user()

    def tearDown(self):
        # clean up orders
        self.mock_order.tear_down_testing_orders()
        # clean up users
        self.mock_user.cleanup()
        os.environ['espa_api_testing'] = ''

    @patch('api.external.lpdaac.get_download_urls', lpdaac.get_download_urls)
    @patch('api.providers.ordering.production_provider.ProductionProvider.set_product_retry', mock_production_provider.set_product_retry)
    def test_fetch_production_products_modis(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        # need scenes with statuses of 'processing' and 'ordered'
        self.mock_order.update_scenes(order_id, 'status', ['processing', 'ordered', 'oncache'])
        user = User.where("id = {0}".format(self.user_id))[0]
        params = {'for_user': user.username, 'product_types': ['modis']}

        # api.fetch_production_products calls to ->
        response = production_provider.get_products_to_process(**params)
        self.assertTrue('bilbo' in response[0]['orderid'])

    @patch('api.external.lta.get_download_urls', lta.get_download_urls)
    @patch('api.providers.ordering.production_provider.ProductionProvider.set_product_retry',
           mock_production_provider.set_product_retry)
    def test_fetch_production_products_landsat(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        # need scenes with statuses of 'processing' and 'ordered'
        self.mock_order.update_scenes(order_id, 'status', ['processing','ordered','oncache'])
        user = User.where("id = {0}".format(self.user_id))[0]
        params = {'for_user': user.username, 'product_types': ['landsat']}
        response = api.fetch_production_products(params)
        self.assertTrue('bilbo' in response[0]['orderid'])

    def test_production_set_product_retry(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        scene = order.scenes()[0]
        scene.update('retry_count', 4)
        processing_loc = "get_products_to_process"
        error = 'not available after EE call '
        note = 'note this'
        retry_after = datetime.datetime.now() + datetime.timedelta(hours=1)
        retry_limit = 9
        response = production_provider.set_product_retry(scene.name, order.orderid, processing_loc,
                                                         error, note, retry_after, retry_limit)
        self.assertTrue(response)

    @patch('api.external.lta.update_order_status', mock_production_provider.respond_true)
    @patch('api.system.errors.resolve', errors.resolve_unavailable)
    def test_production_set_product_error_unavailable(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        scene = order.scenes()[0]
        processing_loc = "get_products_to_process"
        error = 'not available after EE call '
        response = production_provider.set_product_error(scene.name, order.orderid,
                                                         processing_loc, error)
        self.assertTrue(response)

    @patch('api.system.errors.resolve', errors.resolve_submitted)
    def test_production_set_product_error_submitted(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        scene = order.scenes()[0]
        processing_loc = "get_products_to_process"
        error = 'not available after EE call '
        response = production_provider.set_product_error(scene.name, order.orderid,
                                                         processing_loc, error)
        self.assertTrue(response)

    @patch('api.providers.ordering.production_provider.ProductionProvider.set_product_retry',
           mock_production_provider.set_product_retry)
    @patch('api.system.errors.resolve', errors.resolve_retry)
    def test_production_set_product_error_retry(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        scene = order.scenes()[0]
        processing_loc = "get_products_to_process"
        error = 'not available after EE call '
        response = production_provider.set_product_error(scene.name, order.orderid,
                                                         processing_loc, error)
        self.assertTrue(response)

    def test_fetch_production_products_plot(self):
        pass

    @patch('api.external.lta.update_order_status', lta.update_order_status)
    @patch('api.providers.ordering.production_provider.ProductionProvider.set_product_retry', mock_production_provider.set_product_retry)
    def test_update_product_details_update_status(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        scene = order.scenes()[0]
        processing_loc = "L8SRLEXAMPLE"
        status = 'Queued'
        response = production_provider.update_product('update_status',
                                                      name=scene.name, orderid=order.orderid,
                                                      processing_loc=processing_loc, status=status)

        self.assertTrue(response)

    @patch('api.external.lta.update_order_status', lta.update_order_status)
    @patch('api.providers.ordering.production_provider.ProductionProvider.set_product_retry', mock_production_provider.set_product_retry)
    # @patch('api.external.onlinecache.capacity', onlinecache.capacity)
    def test_update_product_details_set_product_error(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        scene = order.scenes()[0]
        processing_loc = "L8SRLEXAMPLE"
        error = 'GDAL Warp failed to transform'
        response = production_provider.update_product('set_product_error',
                                                      name=scene.name, orderid=order.orderid,
                                                      processing_loc=processing_loc, error=error)
        self.assertTrue(response)

    @patch('api.external.lta.update_order_status', lta.update_order_status)
    @patch('api.providers.ordering.production_provider.ProductionProvider.set_product_retry', mock_production_provider.set_product_retry)
    def test_update_product_details_set_product_unavailable(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        scene = order.scenes()[0]
        processing_loc = "L8SRLEXAMPLE"
        error = 'include_dswe is an unavailable product option for OLITIRS'
        response = production_provider.update_product('set_product_unavailable',
                                                      name=scene.name, orderid=order.orderid,
                                                      processing_loc=processing_loc, error=error)
        self.assertTrue(response)

    @patch('api.external.lta.update_order_status', lta.update_order_status)
    @patch('api.providers.ordering.production_provider.ProductionProvider.set_product_retry', mock_production_provider.set_product_retry)
    def test_update_product_details_mark_product_complete(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        scene = order.scenes()[0]
        processing_loc = "L8SRLEXAMPLE"
        file_loc = '/some/loc'
        cksum = 'some checksum'
        logfile = 'some log'
        response = production_provider.update_product('mark_product_complete',
                                                      name=scene.name, orderid=order.orderid,
                                                      processing_loc=processing_loc,
                                                      completed_file_location=file_loc,
                                                      cksum_file_location=cksum,
                                                      log_file_contents=logfile)
        self.assertTrue(response)

    @patch('api.providers.ordering.production_provider.ProductionProvider.send_initial_emails',
           mock_production_provider.respond_true)
    @patch('api.providers.ordering.production_provider.ProductionProvider.handle_onorder_landsat_products',
           mock_production_provider.respond_true)
    @patch('api.providers.ordering.production_provider.ProductionProvider.handle_retry_products',
           mock_production_provider.respond_true)
    @patch('api.providers.ordering.production_provider.ProductionProvider.load_ee_orders',
           mock_production_provider.respond_true)
    @patch('api.providers.ordering.production_provider.ProductionProvider.handle_submitted_products',
           mock_production_provider.respond_true)
    @patch('api.providers.ordering.production_provider.ProductionProvider.finalize_orders',
           mock_production_provider.respond_true)
    @patch('api.providers.ordering.production_provider.ProductionProvider.purge_orders',
           mock_production_provider.respond_true)
    def test_handle_orders_success(self):
        response = api.handle_orders()
        self.assertTrue(response)

    @patch('api.external.onlinecache.delete',
           mock_production_provider.respond_true)
    @patch('api.notification.emails.send_purge_report',
           mock_production_provider.respond_true)
    def test_production_purge_orders(self):
        new_completion_date = datetime.datetime.now() - datetime.timedelta(days=12)
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        order.update('status', 'complete')
        order.update('completion_date', new_completion_date)
        response = production_provider.purge_orders()
        self.assertTrue(response)

    # need to figure a test for emails.send_email
    @patch('api.notification.emails.Emails.send_email',
           mock_production_provider.respond_true)
    def test_production_send_initial_emails(self):
        order_id = self.mock_order.generate_testing_order(self.user_id)
        order = Order.where("id = {0}".format(order_id))[0]
        order.update('status', 'ordered')
        response = emails.Emails().send_all_initial()
        self.assertTrue(response)

    def test_production_handle_onorder_landsat_products(self):
        pass

    def test_production_handle_retry_products(self):
        pass

    @patch('api.external.lta.get_available_orders', lta.get_available_orders)
    @patch('api.external.lta.update_order_status', lta.update_order_status)
    @patch('api.external.lta.get_user_name', lta.get_user_name)
    def test_production_load_ee_orders(self):
        production_provider.load_ee_orders()

    def test_production_handle_submitted_products(self):
        pass

    def test_production_finalize_orders(self):
        pass

    def test_handle_orders_fail(self):
        pass

    def queue_products_success(self):
        names_tuple = self.mock_order.names_tuple(3, self.user_id)
        processing_loc = "get_products_to_process"
        job_name = 'jobname49'
        params = {names_tuple, processing_loc, job_name}
        response = api.queue_products(params)
        self.assertTrue(response)

    def get_production_key(self):
        key = 'system_message_title'
        val = api.get_production_key(key)
        self.assertIsInstance(val, str)


if __name__ == '__main__':
    unittest.main(verbosity=2)
