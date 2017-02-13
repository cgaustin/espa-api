import os
import unittest
from mock import patch, MagicMock

from test.version0_testorders import build_base_order
from api.external.nlaps import products_are_nlaps
from api.external import onlinecache
from api.external.mocks import onlinecache as mockonlinecache
from api.external import lta
from api.external.mocks import lta as mocklta
from api.external.hadoop import HadoopHandler

from api.external import lpdaac

class TestLPDAAC(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass



class TestLTA(unittest.TestCase):
    def setUp(self):
        os.environ['espa_api_testing'] = 'True'
        base_order = build_base_order()
        self.scene_ids = [base_order[b].get('inputs', [None]).pop() for b in base_order if type(base_order[b]) == dict]
        self.scene_ids = [s for s in self.scene_ids if s and (s.startswith('L'))]  # Landsat only

    def tearDown(self):
        os.environ['espa_api_testing'] = ''

    @patch('api.external.lta.requests.post', mocklta.get_verify_scenes_response)
    def test_verify_scenes(self):
        resp = lta.verify_scenes(self.scene_ids)
        for item in self.scene_ids:
           self.assertTrue(item in resp.keys())
           self.assertTrue(resp[item])

    @patch('api.external.lta.requests.post')
    def test_verify_scenes_fail(self, mock_requests):
        mock_requests.return_value = MagicMock(ok=False, reason='Testing Failure')
        with self.assertRaises(Exception):
            resp = lta.verify_scenes(self.scene_ids)

    @patch('api.external.lta.requests.post', mocklta.get_order_scenes_response_main)
    def test_order_scenes(self):
        contact_id = 11111111
        resp = lta.order_scenes(self.scene_ids, contact_id)
        self.assertIn('ordered', resp)
        self.assertEqual(len(self.scene_ids), len(resp['ordered']))


    #@patch('api.external.lta.OrderUpdateServiceClient.update_order', mocklta.return_update_order_resp)
    @patch('api.external.lta.SoapClient', mocklta.get_available_orders_response)
    def test_get_available_orders(self):
        resp = lta.get_available_orders()
        self.assertTrue(len(resp) == 0)


class TestNLAPS(unittest.TestCase):
    """
    Provide testing for sorting out NLAPS products
    """
    def setUp(self):
        self.nlaps = ['LT40150231982306AAA02',
                      'LT40360241982341AAA05',
                      'LT51392101985039AAA03',
                      'LT51790261985079AAA04',
                      'LT50460331985171AAA04']

        self.non_nlaps = ['LT50290302011300PAC01',
                          'LC80300302016065LGN00',
                          'LE70300302016057EDC00',
                          'LE70290302003126EDC00']

    def test_nlaps_prods(self):
        all = [_ for _ in self.nlaps]
        all.extend(self.non_nlaps)

        nlaps_prods = products_are_nlaps(all)

        for prod in nlaps_prods:
            self.assertTrue(prod in self.nlaps)
            self.assertTrue(prod not in self.non_nlaps)


class TestOnlineCache(unittest.TestCase):
    """
    Tests for dealing with the distribution cache
    """
    def setUp(self):
        self.cache = onlinecache.OnlineCache()

    def test_cache_listorders(self):
        results = self.cache.list()

        self.assertTrue(results)

    def test_cache_capcity(self):
        results = self.cache.capacity()

        self.assertTrue('capacity' in results)

    @patch('api.external.onlinecache.OnlineCache.delete', mockonlinecache.delete)
    def test_cache_deleteorder(self):
        results = self.cache.delete('bilbo')
        self.assertTrue(results)


class TestHadoopHandler(unittest.TestCase):
    """
    Tests for the hadoop interaction class
    """
    def setUp(self):
        self.hadoop = HadoopHandler()

    def test_list_jobs(self):
        resp = self.hadoop.list_jobs()
        self.assertTrue('stdout' in resp.keys())

    def test_job_names_ids(self):
        resp = self.hadoop.job_names_ids()
        self.assertTrue(isinstance(resp, dict))

    def test_slave_ips(self):
        resp = self.hadoop.slave_ips()
        self.assertTrue(isinstance(resp, list))
        self.assertTrue(len(resp) > 0)

    def test_master_ip(self):
        resp = self.hadoop.master_ip()
        self.assertTrue(isinstance(resp, str))
        self.assertTrue(len(resp.split('.')) == 4)
