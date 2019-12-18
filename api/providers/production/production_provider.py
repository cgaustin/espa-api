from api.domain import sensor
from api.domain.scene import Scene, SceneException
from api.domain.order import Order, OptionsConversion, OrderException
from api.providers.configuration.configuration_provider import ConfigurationProvider
from api.util.dbconnect import DBConnectException, db_instance
from api.providers.production import ProductionProviderInterfaceV0
from api.providers.caching.caching_provider import CachingProvider
from api.external import inventory, onlinecache
from api.system import errors
from api.notification import emails
from api.domain.user import User
from api import util as utils

import copy
import datetime
import urllib.parse
import json
import socket
import os
import re
import requests

from api.system.logger import ilogger as logger

config = ConfigurationProvider()
cache = CachingProvider()


class ProductionProviderException(Exception):
    pass


class ProductionProvider(ProductionProviderInterfaceV0):

    def queue_products(self, order_name_tuple_list, processing_location, job_name):
        """
        Allows the caller to place products into queued status in bulk
        :param order_name_tuple_list: list of tuples, ie [(orderid, scene_name), ...]
        :param processing_location: location of request to queue products
        :param job_name: name of job
        :return: True
        """
        if not isinstance(order_name_tuple_list, list):
            msg = list()
            msg.append("queue_products expects a list of ")
            msg.append("tuples(orderid, scene_name) for the first argument")
            raise TypeError(''.join(msg))

        # this should be a dictionary of lists, with order as the key and
        # the scenes added to the list
        orders = {}

        for order, product_name in order_name_tuple_list:
            if not order in orders:
                orders[order] = list()
            orders[order].append(product_name)

        # now use the orders dict we built to update the db
        for order in orders:
            product_tup = tuple(str(p) for p in orders[order])
            order = Order.find(order)

            scenes = Scene.where({'order_id': order.id, 'name': product_tup})
            updates = {"status": "queued",
                       "processing_location": processing_location,
                       "log_file_contents": "''",
                       "note": "''",
                       "job_name": job_name}

            Scene.bulk_update([s.id for s in scenes], updates)

        return True

    def mark_product_complete(self, name, orderid, processing_loc=None,
                              completed_file_location=None,
                              destination_cksum_file=None,
                              log_file_contents=None):
        """
        Mark a scene complete
        :param name: name of scene
        :param orderid: order id of scene
        :param processing_loc: where request originated
        :param completed_file_location: where completed product was stored
        :param destination_cksum_file: where product cksum file was stored
        :param log_file_contents: log file contents from processing
        :return: True
        """
        order_status = Scene.get('ordering_order.status', name, orderid)

        order_id = Scene.get('order_id', name, orderid)
        order_source = Scene.get('order_source', name, orderid)
        base_url = config.url_for('distribution.cache')

        product_file = os.path.basename(completed_file_location)
        cksum_file = os.path.basename(destination_cksum_file)

        product_dload_url = ('{}/orders/{}/{}'
                             .format(base_url, orderid, product_file))
        cksum_download_url = ('{}/orders/{}/{}'
                              .format(base_url, orderid, cksum_file))

        scene = Scene.by_name_orderid(name, order_id)

        if order_status == 'cancelled':
            if os.path.exists(completed_file_location):
                scene.download_size = os.path.getsize(completed_file_location)
                onlinecache.delete(orderid, filename=product_file)
                onlinecache.delete(orderid, filename=cksum_file)
            else:
                logger.warning('ERR file was not found: {}'
                                .format(completed_file_location))
            Scene.bulk_update([scene.id], Scene.cancel_opts())
            return False

        scene.status = 'complete'
        scene.processing_location = processing_loc
        scene.product_distro_location = completed_file_location
        scene.completion_date = datetime.datetime.now()
        scene.cksum_distro_location = destination_cksum_file
        scene.log_file_contents = log_file_contents
        scene.product_dload_url = product_dload_url
        scene.cksum_download_url = cksum_download_url
        try:
            scene.download_size = os.path.getsize(completed_file_location)
        except OSError as e:
            # seeing occasional delays in file availability after processing notifies the api of completion
            # raise ProductionProviderException('Could not find completed file location')
            logger.info("mark_product_complete could not find completed file location {}, marking it zero for now...".format(completed_file_location))
            scene.download_size = 0

        if order_source == 'ee':
            token = inventory.get_cached_session()
            # update EE
            ee_order_id = Scene.get('ee_order_id', name, orderid)
            ee_unit_id = Scene.get('ee_unit_id', name, orderid)
            try:
                inventory.update_order_status(token, ee_order_id, ee_unit_id, 'C')
            except Exception as e:
                cache_key = 'lta.cannot.update'
                lta_conn_failed_10mins = cache.get(cache_key)
                if lta_conn_failed_10mins:
                    logger.warn('Problem updating LTA order: {}'.format(e))
                cache.set(cache_key, datetime.datetime.now())
                scene.failed_lta_status_update = 'C'

        try:
            scene.save()
        except DBConnectException as e:
            num, message = e.args
            message = "DBConnect Exception ordering_provider mark_product_complete scene: {0}"\
                        "\nmessage: {1}".format(scene, message)
            raise OrderException(message)

        return True

    def set_product_unavailable(self, name, orderid,
                                processing_loc=None, error=None, note=None):
        """
        Set a product unavailable
        :param name: name of scene to mark unavailable
        :param orderid: order id of scene to mark unavailable
        :param processing_loc: where call to mark scene unavailable originated
        :param error: error message
        :param note: note
        :return: True
        """

        order_id = Scene.get('order_id', name, orderid)
        order_source = Scene.get('order_source', name, orderid)

        scene = Scene.by_name_orderid(name, order_id)
        scene.status = 'unavailable'
        scene.processing_location = processing_loc
        scene.completion_date = datetime.datetime.now()
        scene.log_file_contents = error
        scene.note = note
        scene.save()

        if order_source == 'ee':
            # update EE
            ee_order_id = Scene.get('ee_order_id', name, orderid)
            ee_unit_id = Scene.get('ee_unit_id', name, orderid)
            try:
                token = inventory.get_cached_session()
                inventory.update_order_status(token, ee_order_id, ee_unit_id, 'R')
            except Exception as e:
                cache_key = 'lta.cannot.update'
                lta_conn_failed_10mins = cache.get(cache_key)
                if lta_conn_failed_10mins:
                    logger.warn('Problem updating LTA order: {}'.format(e))
                cache.set(cache_key, datetime.datetime.now())
                scene.failed_lta_status_update = 'R'

        try:
            scene.save()
        except DBConnectException as e:
            num, message = e.args
            msg = "DBConnect Exception ordering_provider set_product_unavailable " \
                      "scene: {0}\nmessage: {1}".format(scene, message)
            raise ProductionProviderException(msg)

        return True

    @staticmethod
    def set_products_unavailable(products, reason):
        """
        Bulk updates products to unavailable status and updates EE if
        necessary.
        :param products: list of Scene objects
        :param reason: user facing explanation for why request was rejected
        :return: True
        """
        try:
            token = inventory.get_cached_session()
            Scene.bulk_update([p.id for p in products],
                              {'status': 'unavailable',
                               'completion_date': datetime.datetime.now(),
                               'note': reason})
            for p in products:
                if p.order_attr('order_source') == 'ee':
                    try:
                        inventory.update_order_status(token, p.order_attr('ee_order_id'), p.ee_unit_id, 'R')
                    except Exception as e:
                        # perhaps this doesn't need to be elevated to 'debug' status
                        # as its a fairly regular occurrence
                        logger.warn('Problem updating LTA order: {}'.format(e))
                        p.update('failed_lta_status_update', 'R')
        except Exception as e:
            raise ProductionProviderException(e)

        return True

    def update_status(self, name, orderid, processing_loc=None, status=None):
        """
        Update the status for a scene give its name, and order_id
        :param name: name of scene to update
        :param orderid: the order id of scene to update
        :param processing_loc: where in processing the status is being updated from
        :param status: what the status is to be set to
        :return: True
        """
        order = Order.find(orderid)
        scene = Scene.by_name_orderid(name, order.id)
        if order.status == 'cancelled':
            Scene.bulk_update([scene.id], Scene.cancel_opts())
            return False
        if processing_loc:
            scene.processing_location = processing_loc
        if status:
            scene.status = status
        scene.save()
        log_str = "Scene status updated. order: {0}\n scene id/name: {1}/{2}\nstatus:{3}\nprocessing_location{4}\n "
        logger.info(log_str.format(order.orderid, scene.id, scene.name, scene.status, scene.processing_location))
        return True

    def update_product(self, action, name=None, orderid=None,
                       processing_loc=None, status=None, error=None,
                       note=None, completed_file_location=None,
                       cksum_file_location=None, log_file_contents=None):
        """
        Update a scene's status to error, unavailable, complete, or something else

        :param action: name of the action to perform
        :param name: name of the scene to perform action on
        :param orderid: order id of the scene to perform action on
        :param processing_loc: where the request to perform the action came from
        :param status: new scene status
        :param error: new error message
        :param note: new note value
        :param completed_file_location: where finished product is stored
        :param cksum_file_location: where cksum file for product is stored
        :param log_file_contents: new log file contents
        :return: True
        """
        if action == 'update_status':
            result = self.update_status(name, orderid,
                                        processing_loc=processing_loc,
                                        status=status)

        elif action == 'set_product_error':
            result = self.set_product_error(name, orderid,
                                            processing_loc=processing_loc,
                                            error=error)

        elif action == 'set_product_unavailable':
            result = self.set_product_unavailable(name, orderid,
                                                  processing_loc=processing_loc,
                                                  error=error, note=note)

        elif action == 'mark_product_complete':
            result = self.mark_product_complete(name, orderid,
                                                processing_loc=processing_loc,
                                                completed_file_location=completed_file_location,
                                                destination_cksum_file=cksum_file_location,
                                                log_file_contents=log_file_contents)

        else:
            result = {'msg': ('{} is not an accepted action for '
                              'update_product'.format(action))}

        return result

    def set_product_retry(self, name, orderid, processing_loc,
                          error, note, retry_after, retry_limit=None):
        """
        Set a product into retry status

        :param name: scene/collection name
        :param orderid: order id, longname
        :param processing_loc: processing computer name
        :param error: error log
        :param note: note to update
        :param retry_after: retry after given timestamp
        :param retry_limit: maximum number of tries
        """
        order = Order.find(orderid)
        scene = Scene.by_name_orderid(name, order.id)

        retry_count = scene.retry_count if scene.retry_count else 0

        if not retry_limit:
            retry_limit = scene.retry_limit

        # make sure retry_limit and retry_count are ints
        retry_count = int(retry_count)
        retry_limit = int(retry_limit)
        new_retry_count = retry_count + 1

        if new_retry_count > retry_limit:
            raise ProductionProviderException('Retry limit exceeded, name: {}'.format(name))

        scene.status = 'retry'
        scene.retry_count = new_retry_count
        scene.retry_after = retry_after
        scene.retry_limit = retry_limit
        scene.log_file_contents = error
        scene.processing_location = processing_loc
        scene.note = note
        scene.save()

        return True

    def set_product_error(self, name, orderid, processing_loc, error):
        """
        Marks a scene in error and accepts the log file contents
        :param name: name of scene to update
        :param orderid: order id of scene to update
        :param processing_loc: where command to update scene came from
        :param error: error message from processing
        :return: True
        """
        order = Order.find(orderid)
        product = Scene.by_name_orderid(name, order.id)
        #attempt to determine the disposition of this error
        resolution = None

        if product.status == 'complete':
            # Mesos tasks occasionaly exit abnormally, even though processing completed successfully.
            # When that happens, the ESPA framework will try to set the scene to error status
            logger.error("Received set_product_error request for a complete product!\nOrder ID: {}\nProduct: {}".format(orderid, name))
            return {"error": "attempted to set scene to error that was already marked complete"}

        if name != 'plot':
            resolution = errors.resolve(error, name)

        logger.info("\n\n*** set_product_error: orderid {0}, "
                    "scene id {1} , scene name {2},\n"
                    "error {4!r},\n"
                    "resolution {3}\n\n".format(order.orderid, product.id,
                                                product.name, resolution, error))

        if resolution is not None:
            if resolution.status == 'submitted':
                product.status = 'submitted'
                product.note = ''
                product.save()
            elif resolution.status == 'unavailable':
                self.set_product_unavailable(product.name,
                                             order.orderid,
                                             processing_loc,
                                             error,
                                             resolution.reason)
            elif resolution.status == 'retry':
                try:
                    self.set_product_retry(product.name,
                                           order.orderid,
                                           processing_loc,
                                           error,
                                           resolution.reason,
                                           resolution.extra['retry_after'],
                                           resolution.extra['retry_limit'])
                except Exception as e:
                    logger.info('Exception setting product.id {} {} '
                                 'to retry: {}'
                                 .format(product.id, name, e))
                    product.status = 'error'
                    product.processing_location = processing_loc
                    product.log_file_contents = error
                    product.save()
        else:
            product.status = 'error'
            product.processing_location = processing_loc
            product.log_file_contents = error
            product.save()

        return True

    def converted_opts(self, scene_id, product_opts):
        if scene_id == 'plot':
            options = {}
        elif config.get('convertprodopts') == 'True':
            options = OptionsConversion.convert(new=product_opts, scenes=[scene_id])
        else:
            # Need to strip out everything not directly related to the scene
            options = self.strip_unrelated(scene_id, product_opts)
        return options

    def parse_urls_m2m(self, query_results, encode_urls=False):

        results = [{'orderid': r['orderid'],
                    'product_type': r['sensor_type'],
                    'scene': r['name'],
                    'priority': r['priority'],
                    'options': self.converted_opts(r['name'], r['product_opts'])
                    } for r in query_results]

        non_plot_ids = [r['name'] for r in query_results if r['sensor_type'] != 'plot']

        if non_plot_ids:
            urls = dict()
            unavailable, available = list(), list()
            token = inventory.get_session()
            for dataset, ids in inventory.split_by_dataset(non_plot_ids).items():
                try:
                    verified = inventory.verify_scenes(token, ids, dataset)
                    # {'LT04_L1TP_007057_19871226_20170210_01_T1': True, 'LT04_L1TP_007057_19880111_20170210_01_T1': False, ...}
                    for _id, _availability in verified.items():
                        available.append(_id) if _availability else unavailable.append(_id)
                    if unavailable:
                        logger.warn('Unavailable Scenes found in request for download urls. Marking unavailable ids: {0}\n'.format(unavailable))
                        unavailable_scenes = Scene.where({'name': unavailable})
                        self.set_products_unavailable(unavailable_scenes, "Scene no longer available")
                    urls.update(inventory.download_urls(token, available, dataset))
                except Exception as e:
                    logger.error('Problem getting URLs: {}'.format(e), exc_info=True)
            if encode_urls:
                urls = {k: urllib.parse.quote(u, '') for k, u in urls.items()}

            results = [dict(r, download_url=urls.get(r['scene']))
                            if r['scene'] in non_plot_ids else r for r in results]

            results = [r for r in results if 'download_url' in r and r.get('download_url')]

        return results


    def query_pending_products(self, record_limit=500, for_user=None,
                               priority=None, product_types=['landsat', 'modis', 'viirs', 'sentinel']):
        sql = [
            'WITH order_queue AS',
                '(SELECT u.email "email", count(name) "running"',
                'FROM ordering_scene s',
                'JOIN ordering_order o ON o.id = s.order_id',
                'JOIN auth_user u ON u.id = o.user_id',
                'WHERE s.status in %(running_s_status)s',
                'GROUP BY u.email)',
            'SELECT u.contactid, s.name, s.sensor_type,',
                'o.orderid, o.product_opts, o.priority,',
                'o.order_date, q.running',
            'FROM ordering_scene s',
            'JOIN ordering_order o ON o.id = s.order_id',
            'JOIN auth_user u ON u.id = o.user_id',
            'LEFT JOIN order_queue q ON q.email = u.email',
            'WHERE',
                'o.status = %(order_status)s',
                'AND s.status = %(s_status)s',
        ]
        params = {
            'running_s_status': ("queued", "processing"),
            'order_status': 'ordered',
            's_status': 'oncache',
        }

        if not isinstance(product_types, list):
            # unicode values of either: u"['plot']" or u"['landsat', 'modis', 'viirs', 'sentinel']"
            product_types = json.loads(str(product_types).replace("'", '"'))

        if isinstance(product_types, list) and len(product_types) > 0:
            sql += ['AND s.sensor_type IN %(product_types)s']
            params['product_types'] = tuple(product_types)

        if for_user is not None:
            sql += ['AND u.username = %(for_user)s']
            params['for_user'] = for_user

        if priority is not None:
            sql += ['AND o.priority = %(priority)s']
            params['priority'] = priority

        sql += ['ORDER BY q.running ASC NULLS FIRST,']
        sql += ['o.order_date ASC LIMIT %(record_limit)s']
        params['record_limit'] = record_limit

        query = ' '.join(sql)

        with db_instance() as db:
            log_sql = db.cursor.mogrify(query, params)
            logger.warn("QUERY:{0}".format(log_sql))
            db.select(query, params)

        # Columns: ['contactid', 'name', 'sensor_type', 'orderid',
        #           'product_opts', 'priority', 'order_date', 'running']
        return db.fetcharr


    def get_products_to_process(self, record_limit=500,
                                for_user=None,
                                priority=None,
                                product_types=['landsat', 'modis', 'viirs', 'sentinel'],
                                encode_urls=False):
        """
        Find scenes that are oncache and return them as properly formatted
        json per the interface description between the web and processing tier
        :param record_limit: max number of scenes to retrieve
        :param for_user: the user whose scenes to retrieve
        :param priority: the priority of scenes to retrieve
        :param product_types: types of products to retrieve
        :param encode_urls: whether to encode the urls
        :return: list
        """
        logger.info('Retrieving products to process...')
        logger.warn('Record limit:{0}'.format(record_limit))
        logger.warn('Priority:{0}'.format(priority))
        logger.warn('For user:{0}'.format(for_user))
        logger.warn('Product types:{0}'.format(product_types))
        logger.warn('Encode urls:{0}'.format(encode_urls))

        query_results = self.query_pending_products(
            record_limit=record_limit, for_user=for_user, priority=priority,
            product_types=product_types)

        if not inventory.available():
            logger.error('M2M down. Unable to get download URLs')
        else:
            return self.parse_urls_m2m(query_results)

    def load_ee_orders(self, contact_id=None):
        """
        Loads all the available orders from lta into
        our database and updates their status
        """
        if config.get('system.load_ee_orders_enabled').lower() == 'false':
            logger.info('system.load_ee_orders_enabled is disabled, skipping load_ee_orders()')
            return

        def find_espa_order(ordernumber):
            _orders = Order.where({'ee_order_id': ordernumber})
            return _orders[0] if _orders else []

        ipaddr    = socket.gethostbyaddr(socket.gethostname())[2][0]
        token     = inventory.get_cached_session()
        ee_orders = [utils.conv_dict(i) for i in inventory.get_available_orders(token, contact_id)]

        logger.info('load_ee_orders - Number of ESPA orders in EE: {}'.format(len(ee_orders)))

        for ee_order in ee_orders:
            scene_info = [utils.conv_dict(i) for i in ee_order.get('units')]
            contactid    = str(ee_order.get('contactId'))
            order_number = ee_order.get('orderNumber')
            espa_order   = find_espa_order(order_number)

            if espa_order: # EE order already exists in the system, update the associated scenes 
                self.update_ee_orders(scene_info, order_number, espa_order.id)
            else:
                logger.debug("load_ee_orders - new espa order from EE. scene: {}, contactid: {}, order_number: {}".format(scene_info, contactid, order_number))
                user = User.by_contactid(contactid)

                if user is None:
                    logger.debug("load_ee_orders - unable to find user in espa, create them: ")
                    try:
                        username, email_addr = inventory.get_user_details(token, contactid, ipaddr)
                        # Find or create the user
                        user = User(username, email_addr, 'from', 'earthexplorer', contactid)
                        #cache.set(cache_key, user, 43200) # 12 hours -> 60 * 60 * 12
                        logger.debug("load_ee_orders - created user, username: {}".format(user.username))
                    except inventory.LTAError as e:
                        logger.error("load_ee_orders - LTAError: Unable to retrieve user name for contactid {}. exception: {}".format(contactid, e))

                if user:
                    # We have a user now.  Now build the new Order since it wasn't found
                    logger.debug("load_ee_orders - we have a user, build the order. email: {}  order_number: {}".format(user.email, order_number))
                    order_dict = {'orderid': Order.generate_ee_order_id(user.email, order_number),
                                  'user_id': user.id,
                                  'order_type': 'level2_ondemand',
                                  'status': 'ordered',
                                  'note': 'EarthExplorer order id: {}'.format(order_number),
                                  'ee_order_id': order_number,
                                  'order_source': 'ee',
                                  'order_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                                  'priority': 'normal',
                                  'email': user.email,
                                  'product_options': 'include_sr: true',
                                  'product_opts': Order.get_default_ee_options(scene_info)}
                    order = Order.create(order_dict)
                    self.load_ee_scenes(scene_info, order.id)
                    self.update_ee_orders(scene_info, order_number, order.id)
                else:
                    logger.debug("unable to import EE order: eeorder {} contactid {}".format(order_number, contactid))
        
    @staticmethod
    def gen_ee_scene_list(ee_scenes, order_id):
        """
        Return formatted list of dictionaries used to insert
        scene records from EE orders

        ee_scenes = [{'sceneid': xxx , 'unit_num': iii }]

        :param ee_scenes: list of scenes to insert into the db
        :param order_id: the id of the order the scenes belong to
        :return: list of dictionaries, used for generating scene records
        """
        bulk_ls = []
        for s in ee_scenes:
            product = sensor.instance(s['orderingId'])

            sensor_type = ''
            if isinstance(product, sensor.Landsat):
                sensor_type = 'landsat'
            elif isinstance(product, sensor.Modis):
                sensor_type = 'modis'

            status = 'oncache'
            note = ''
            # All EE orders are for SR, require auxiliary data
            if product.sr_date_restricted():
                status = 'unavailable'
                note = 'Missing Auxiliary data - cannot process SR'
                logger.info('check ee unavailable: {}'.format(product.__dict__))

            scene_dict = {'name': product.product_id,
                          'sensor_type': sensor_type,
                          'order_id': order_id,
                          'status': status,
                          'note': note,
                          'ee_unit_id': s['unitNumber']}
            logger.info('check ee processing: {}'.format(scene_dict))

            bulk_ls.append(scene_dict)
        return bulk_ls

    def load_ee_scenes(self, ee_scenes, order_id, missed=None):
        """
        Load the associated EE scenes into the system for processing

        ee_scenes_example = [{'sceneid': xxx, 'unit_num': iii}]

        :param ee_scenes: list of scenes to place in the DB
        :param order_id: numeric ordering_order.id associated with the
          scenes
        :param missed: used to indicate adding missing scenes to existing
          order
        """
        bulk_ls = self.gen_ee_scene_list(ee_scenes, order_id)
        try:
            Scene.create(bulk_ls)
            for params in bulk_ls:
                # Add the note from the scene_dict in bulk_ls, not included in Scene.create()
                scene = Scene.by_name_orderid(name=params['name'], order_id=params['order_id'])
                scene.note = params['note']
                scene.save()
        except (SceneException, sensor.ProductNotImplemented) as e:
            num, message = e.args
            if missed:
                # we failed to load scenes missed on initial EE order import
                # we do not want to delete the order, as we would on initial
                # creation
                logger.critical('EE Scene creation failed on scene injection, '
                                'for missing EE scenes on existing order '
                                'order: {}\nexception: {}'.format(order_id, message))
            else:
                logger.critical('EE Order creation failed on scene injection, '
                                'order: {}\nexception: {}'
                                .format(order_id, message))

                with db_instance() as db:
                    db.execute('delete ordering_order where id = %s',
                               order_id)
                    db.commit()

            raise ProductionProviderException(e)

    def update_ee_orders(self, ee_scenes, eeorder_num, order_id):
        """
        Update the LTA tracking system with the current status of
        a product in the system

        ee_scenes_example = [{'sceneid': ,
                              'unit_num': }]

        :param ee_scenes: list of dicts
        :param eeorder_num: associated EE order id
        :param order_id: order id used in the system
        """
        missing_scenes = []
        scenes = Scene.where({'order_id': order_id,
                              'ee_unit_id': tuple([s['unitNumber'] for s in ee_scenes])})
        token = inventory.get_cached_session()
        for s in ee_scenes:
            unit_number = s['unitNumber']
            unit_scenes = [so for so in scenes if so.ee_unit_id == unit_number]

            if unit_scenes:
                scene = unit_scenes[0]
                if scene.status == 'complete':
                    status = 'C'
                elif scene.status in ('unavailable', 'cancelled'):
                    status = 'R'
                else:
                    status = 'I'
                    continue  # No need to update scenes in progress
                try:
                    inventory.update_order_status(token, eeorder_num, unit_number, status)
                except Exception as e:
                    cache_key = 'lta.cannot.update'
                    lta_conn_failed_10mins = cache.get(cache_key)
                    if lta_conn_failed_10mins:
                        logger.warn("Error updating lta for scene: {}\n{}".format(scene.id, e))
                    cache.set(cache_key, datetime.datetime.now())
                    scene.update('failed_lta_status_update', status)
            else:
                # scene insertion was missed initially, add it now
                missing_scenes.append(s)

        if missing_scenes:
            # There appear to be scenes in this order which we didn't receive the
            # first go around, try adding them now
            order = Order.find(order_id)
            order.update('product_opts', json.dumps(Order.get_default_ee_options(ee_scenes)))

            self.load_ee_scenes(missing_scenes, order_id, missed=True)

    def handle_retry_products(self, products):
        """
        Handle all products in retry status
        :return: True
        """
        try:
            if len(products) > 0:
                Scene.bulk_update([p.id for p in products], {'status': 'submitted', 'note': ''})
        except Exception as e:
            raise ProductionProviderException("error with handle_retry_products: {}".format(e))

        return True

    @staticmethod
    def handle_cancelled_orders(params):
        """ Find all orders without cancelled order email sent, and sends them
        :return: True
        """
        orders = Order.where(params)
        for order in orders:
            scenes = order.scenes()
            processing = [s for s in scenes if s.status in ['scheduled', 'tasked', 'processing']]
            if processing:
                logger.warn("Cancelled order %s has scenes processing, waiting to delete" % order.orderid)
            else:
                if not order.completion_email_sent:
                    if onlinecache.exists(order.orderid):
                        onlinecache.delete(order.orderid)
                    if order.order_source == 'espa':
                        emails.Emails().send_order_cancelled_email(order.orderid)
                        order.update('completion_email_sent', datetime.datetime.now())
        return True

    def handle_onorder_landsat_products(self, products):
        """
        Handles landsat products still on order
        :return: True
        """
        # lets control how many scenes were going to ping LTA for status updates
        # every 7 (currently) minutes
        # tram_order_id is sequential (looks like a timestamp), so we can sort
        # by that, running with the 'oldest' orders assuming they process FIFO
        # converting to a set eliminates duplicate calls to lta
        product_tram_ids = set([product.tram_order_id for product in products])
        sorted_tram_ids = sorted(product_tram_ids)[:500]

        rejected = []
        available = []

        token = inventory.get_cached_session()

        for tid in sorted_tram_ids:
            order_status = inventory.get_order_status(token, tid)

            # There are a variety of product statuses that come back from tram
            # on this call.  I is inprocess, Q is queued for the backend system,
            # D is duplicate, C is complete and R is rejected.  We are ignoring
            # all the statuses except for R and C because we don't care.
            # In the case of D (duplicates), when the first product completes, all
            # duplicates will also be marked C
            for unit in order_status['units']:
                if unit['statusCode'] == 'R':
                    rejected.append(unit['orderingId']) # or 'displayId', 'entityId'
                elif unit['statusCode'] == 'C':
                    available.append(unit['orderingId'])

        # Go find all the tram units that were rejected and mark them
        # unavailable in our database.  Note that we are not looking for
        # specific tram_order_id/sceneids as duplicate tram orders may have been
        # submitted and we want to bulk update all scenes that are onorder but
        # have been rejected
        if len(rejected) > 0:
            rejected_products = [p for p in products if p.name in rejected]
            # scene may not be rejected or complete
            if rejected_products:
                self.set_products_unavailable(rejected_products, 'Level 1 product could not be produced')

        if len(available) > 0:
            products = [a for a in products if a.name in available]
            # scene may not be rejected or complete
            if products:
                Scene.bulk_update([p.id for p in products], {'status': 'oncache', 'note': ''})

        return True

    def send_initial_emails(self, orders):
        """
        ProductionProvider wrapper for Emails.send_all_initial
        :return: True
        """
        return emails.Emails().send_all_initial(orders)

    @staticmethod
    def get_contactids_for_submitted_landsat_products(scenes):
        """
        Assembles a list of contactids for submitted landsat products
        :return: list
        """
        logger.info("Retrieving contact ids for submitted landsat products")
        if scenes:
            user_ids = [s.order_attr('user_id') for s in scenes]
            users = User.where({'id': tuple(user_ids)})
            contact_ids = set([user.contactid for user in users])
            logger.info("Found contact ids:{0}".format(contact_ids))
            return contact_ids
        else:
            return []

    @staticmethod
    def check_dependencies_for_products(scene_list):
        """
        Check if scene/product combination will require external data, and
            filter the list if the service is unreachable at the moment

        :param scene_list: list of api.domain.scene.Scene instances
        :return: list
        """
        products_need_check = {
            'st': config.url_for('modis.datapool')  # ST requires ASTER GED
        }
        passed_dep_check = list()
        for s in scene_list:
            opts = s.order_attr('product_opts')
            sn = sensor.instance(s.name).shortname
            prods = opts[sn]['products']
            passed_all = True
            for p in prods:
                need_check = p in products_need_check
                if need_check:
                    passed_all &= utils.connections.is_reachable(products_need_check[p], timeout=4)
            if passed_all:
                passed_dep_check.append(s)
        return passed_dep_check

    def handle_submitted_landsat_products(self, scenes):
        """
        Handles all submitted landsat products
        :return: True
        """
        if not inventory.available():
            logger.warning('M2M down. Skip handle_submitted_landsat_products...')
            return False

        try:
            logger.info('Handling submitted landsat products...')

            token = inventory.get_cached_session()
            prod_name_list, valid, invalid = set(), set(), set()

            for s in scenes:
                prod_name_list.add(s.name)

            for r, v in inventory.check_valid(token, prod_name_list).items():
                valid.add(r) if v else invalid.add(r)

            for scene in scenes:
                if scene.name in valid:
                    scene.status = 'oncache'
                    scene.note = "''"
                    scene.save()
                else:
                    scene.status = 'unavailable'
                    scene.note = 'No longer found in the archive, please search again'
                    scene.save()
        except Exception as e:
            msg = ('Exception running handle_submitted_landsat_products: {}'.format(e))
            logger.critical(msg)

        return True

    def handle_submitted_modis_products(self, modis_products):
        """
        Moves all submitted modis products to oncache if true
        :return: True
        """
        if not inventory.available():
            logger.warning('M2M down. Skip handle_submitted_modis_products...')
            return False
        logger.info("Handling submitted modis products...")

        logger.warn("Found {0} submitted modis products".format(len(modis_products)))

        if len(modis_products) > 0:
            lpdaac_ids = []
            nonlp_ids = []

            prod_name_list = [p.name for p in modis_products]
            token = inventory.get_cached_session()
            results = inventory.check_valid(token, prod_name_list)
            valid = list(set(r for r,v in results.items() if v))
            invalid = list(set(prod_name_list)-set(valid))

            available_ids = [p.id for p in modis_products if p.name in valid]
            if len(available_ids):
                Scene.bulk_update(available_ids, {'status': 'oncache', 'note': "''"})

            invalids = [p for p in modis_products if p.name in invalid]
            if len(invalids):
                self.set_products_unavailable(invalids, 'No longer found in the archive, please search again')

        return True

    def handle_submitted_sentinel_products(self, sentinel_products):
        """
        Moves all submitted sentinel products to oncache if true
        :return: True
        """
        if not inventory.available():
            logger.warning('M2M down. Skip handle_submitted_sentinel_orders...')
            return False
        logger.info("Handling submitted sentinel products...")

        logger.warn("Found {0} submitted sentinel products".format(len(sentinel_products)))

        if len(sentinel_products) > 0:
            prod_name_list = [p.name for p in sentinel_products]
            token = inventory.get_cached_session()
            results = inventory.check_valid(token, prod_name_list)
            valid = list(set(r for r, v in results.items() if v))
            invalid = list(set(prod_name_list) - set(valid))

            available_ids = [p.id for p in sentinel_products if p.name in valid]
            if len(available_ids):
                Scene.bulk_update(available_ids, {'status': 'oncache', 'note': "''"})

            invalids = [p for p in sentinel_products if p.name in invalid]
            if len(invalids):
                self.set_products_unavailable(invalids, 'No longer found in the archive, please search again')

        return True


    def handle_submitted_viirs_products(self, viirs_products):
        """
        Moves all submitted viirs products to oncache if true
        :return: True
        """
        if not inventory.available():
            logger.warning('M2M down. Skip handle_submitted_viirs_products...')
            return False
        logger.info("Handling submitted viirs products...")

        logger.warn("Found {0} submitted viirs products".format(len(viirs_products)))

        if len(viirs_products) > 0:
            lpdaac_ids = []
            nonlp_ids = []

            prod_name_list = [p.name for p in viirs_products]
            token = inventory.get_cached_session()
            results = inventory.check_valid(token, prod_name_list)
            valid = list(set(r for r,v in results.items() if v))
            invalid = list(set(prod_name_list)-set(valid))

            available_ids = [p.id for p in viirs_products if p.name in valid]
            if len(available_ids):
                Scene.bulk_update(available_ids, {'status': 'oncache', 'note': "''"})

            invalids = [p for p in viirs_products if p.name in invalid]
            if len(invalids):
                self.set_products_unavailable(invalids, 'No longer found in the archive, please search again')

        return True

    def handle_submitted_plot_products(self, plot_scenes):
        """
        Moves plot products from submitted to oncache status once all their underlying rasters are complete
        or unavailable
        :return: True
        """
        logger.info("Handling submitted plot products...")

        plot_orders = [Order.find(s.order_id) for s in plot_scenes]
        logger.info("Found {0} submitted plot orders".format(len(plot_orders)))

        for order in plot_orders:
            product_count = order.scene_status_count()
            complete_count = order.scene_status_count('complete')
            unavailable_count = order.scene_status_count('unavailable')

            # if there is only 1 product left that is not done, it must be
            # the plot product. Will verify this in next step.  Plotting
            # cannot run unless everything else is done.
            log_msg = "plot product_count = {}\nplot unavailable count = {}\nplot complete count = {}"
            logger.info(log_msg.format(product_count, unavailable_count, complete_count))

            if product_count - (unavailable_count + complete_count) == 1:
                plots_in_order = order.scenes({'sensor_type': 'plot'})
                if len(plots_in_order) == 1:
                    for p in plots_in_order:
                        if complete_count == 0:
                            p.status = 'unavailable'
                            p.note = 'No input products were available for plotting and statistics'
                            logger.info('No input products available for '
                                        'plotting in order {0}'.format(order.orderid))
                        else:
                            p.status = 'oncache'
                            p.note = ''
                            logger.info("{0} plot is on cache".format(order.orderid))
                        p.save()
                else:
                    logger.critical('{}'.format(plots_in_order))
                    raise ValueError('Too many ({n}) plots in order {oid}'.format(n=len(plots_in_order), oid=order.id))
        return True

    def send_completion_email(self, order):
        """
        Public interface to send the completion email
        :param order: order id
        :return: True
        """
        return emails.Emails().send_completion(order)

    def update_order_if_complete(self, order_id):
        """
        Method to send out the order completion email
        for orders if the completion of a scene
        completes the order
        :param order_id: the order id
        :return: True
        """
        order = order_id if isinstance(order_id, Order) else Order.find(order_id)

        if not type(order) == Order:
            msg = "%s must be of type Order, int or str" % order
            raise TypeError(msg)

        # find all scenes that are not complete
        scenes = order.scenes({'status NOT ': ('complete', 'unavailable')})
        if len(scenes) == 0:
            logger.info('Completing order: {0}'.format(order.orderid))
            #only send the email if this was an espa order.
            if order.order_source == 'espa' and not order.completion_email_sent:
                try:
                    sent = self.send_completion_email(order)
                    order.completion_email_sent = datetime.datetime.now()
                    order.completion_date = datetime.datetime.now()
                    order.status = 'complete'
                    order.save()
                except Exception as e:
                    logger.critical('Error calling send_completion_email\nexception: {}'.format(e))
            else:
                order.completion_date = datetime.datetime.now()
                order.status = 'complete'
                order.save()

        return True

    def calc_scene_download_sizes(self, order_ids):
        """
        Processing occasionally reports product completion before we're able to
        see the download and retrieve its size
        :return: True
        """
        scenes = Scene.where({'status': 'complete', 'download_size': 0, 'order_id': order_ids})
        for scene in scenes:
            if os.path.exists(scene.product_distro_location):
                scene.update('download_size', os.path.getsize(scene.product_distro_location))
            else:
                scene.status = 'error'
                scene.note = 'product download not found'
                scene.save()
                logger.critical("scene download size re-calcing failed, {}"
                                .format(scene.product_distro_location))

        return True

    def finalize_orders(self, orders):
        """
        Checks all open orders in the system and marks them complete if all
        required scene processing is done
        :return: True
        """
        [self.update_order_if_complete(o) for o in orders]
        return True

    def purge_orders(self, send_email=False):
        """
        Will move any orders older than X days to purged status and will also
        remove the files from disk
        :param send_email: boolean
        :return: True
        """
        days = config.get('policy.purge_orders_after')
        cutoff = datetime.datetime.now() - datetime.timedelta(days=int(days))
        orders = Order.where({'status': 'complete', 'completion_date <': cutoff})
        start_capacity = onlinecache.capacity()

        logger.info('Using purge policy of {0} days'.format(days))
        logger.info('Purging {0} orders from the active record.'.format(len(orders)))
        logger.info('Starting cache capacity:{0}'.format(start_capacity))

        for order in orders:
            try:
                #with transaction.atomic():
                order.update('status', 'purged')
                for product in order.scenes():
                    product.status = 'purged'
                    product.log_file_contents = ''
                    product.product_distro_location = ''
                    product.product_dload_url = ''
                    product.cksum_distro_location = ''
                    product.cksum_download_url = ''
                    product.job_name = ''
                    product.save()

                if onlinecache.exists(order.orderid):
                    # bulk update product status, delete unnecessary field data
                    logger.info('Deleting {0} from online cache disk'.format(order.orderid))
                    onlinecache.delete(order.orderid)
            except onlinecache.OnlineCacheException:
                logger.critical('Could not delete {0} from the online cache'.format(order.orderid))
            except Exception as e:
                logger.critical('Exception purging {0}\nexception: {1}'.format(order.orderid, e))

        end_capacity = onlinecache.capacity()
        logger.info('Ending cache capacity:{0}'.format(end_capacity))

        orders = [{o.orderid: len(o.scenes())} for o in orders]
        if send_email is True:
            logger.info('Sending purge report')
            emails.send_purge_report(start_capacity, end_capacity, orders)

        return True

    @staticmethod
    def handle_failed_ee_updates(scenes):
        n_failed = len(scenes)
        token = inventory.get_cached_session()
        if n_failed:
            logger.critical('Failed LTA status count: {} scenes'.format(n_failed))
        for s in scenes:
            try:
                inventory.update_order_status(token, s.order_attr('ee_order_id'), s.ee_unit_id,
                                              s.failed_lta_status_update)
                s.update('failed_lta_status_update', None)
            except DBConnectException as e:
                raise ProductionProviderException('ordering_scene update failed for '
                                                  'handle_failed_ee_updates: {}'.format(e))
            except Exception as e:
                # LTA could still be unavailable, log and it'll be tried again later
                logger.warn('Failed EE update retry failed again for '
                            'scene {}\n{}'.format(s.id, e))
        return True

    def handle_orders(self, username=None):
        """
        Logic handler for how we accept orders + products into the system
        :return: True
        """
        filters = {'status': 'ordered'}

        user = None
        if username:
            user = User.by_username(username)
            logger.warn('@USER {} ({})'.format(user.username, user.email))
            filters.update(user_id=user.id)

        contactid = user.contactid if user else None
        try:
            self.load_ee_orders(contactid)
        except Exception as e:
            logger.debug("Unable to load_ee_orders: {}".format(e))

        pending_orders = Order.where(filters)
        pending_order_ids = [o.id for o in pending_orders]

        if len(pending_orders) < 1:
            logger.error('No pending orders found: {}'.format(filters))
            return False
        logger.info('# Pending orders to handle: {}'.format(len(pending_orders)))

        # send confirmation emails for new orders
        orders_send_email = [i for i in pending_orders if i.initial_email_sent is None]
        if len(orders_send_email):
            self.send_initial_emails(orders_send_email)
        orders_send_email = None

        # handle landsat products still on order
        products = Scene.where({'status': 'onorder', 'tram_order_id IS NOT': None, 'order_id': pending_order_ids})
        self.handle_onorder_landsat_products(products)

        # handle orphaned Mesos tasks
        time_jobs_stuck = datetime.datetime.now() - datetime.timedelta(hours=6)
        products = Scene.where({'status': ('tasked', 'scheduled', 'processing'), 'status_modified <': time_jobs_stuck})
        self.handle_stuck_jobs(products)

        # handle retry products
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        retry_products = Scene.where({'status': 'retry', 'retry_after <': now, 'order_id': pending_order_ids})
        self.handle_retry_products(retry_products)
        retry_products = None

        # handle failed EE order updates
        scenes = Scene.where({'failed_lta_status_update IS NOT': None, 'order_id': pending_order_ids})
        self.handle_failed_ee_updates(scenes)
        scenes = None

        # handle cancelled orders
        days = config.get('policy.purge_orders_after')
        cutoff = datetime.datetime.now() - datetime.timedelta(days=int(days))
        search = {'status': 'cancelled',  'completion_email_sent IS': None, 'order_date >': cutoff}
        if user:
                search.update(user_id=user.id)
        self.handle_cancelled_orders(search)

        # retrieve all scenes in submitted state
        submitted_scenes = Scene.where({'status': 'submitted', 'order_id': pending_order_ids})

        submitted_landsat = [s for s in submitted_scenes if s.sensor_type == 'landsat'][:500]
        self.handle_submitted_landsat_products(submitted_landsat)
        submitted_landsat = None

        submitted_modis = [s for s in submitted_scenes if s.sensor_type == 'modis']
        self.handle_submitted_modis_products(submitted_modis)
        submitted_modis = None

        submitted_viirs = [s for s in submitted_scenes if s.sensor_type == 'viirs']
        self.handle_submitted_viirs_products(submitted_viirs)
        submitted_viirs = None

        submitted_sentinel = [s for s in submitted_scenes if s.sensor_type == 'sentinel']
        self.handle_submitted_sentinel_products(submitted_sentinel)
        submitted_sentinel = None

        submitted_plot = [s for s in submitted_scenes if s.sensor_type == 'plot']
        self.handle_submitted_plot_products(submitted_plot)
        submitted_plot = None

        self.calc_scene_download_sizes(pending_order_ids)

        # finalize orders
        for order in pending_orders:
            self.update_order_if_complete(order)

        cache_key = 'orders_last_purged'
        result = cache.get(cache_key)

        # dont run this unless the cached lock has expired
        if result is None:
            logger.info('Purge lock expired... running')

            # first thing, populate the cached lock field
            timeout = int(config.get('system.run_order_purge_every'))
            cache.set(cache_key, datetime.datetime.now(), timeout)

            #purge the orders from disk now
            self.purge_orders(send_email=True)
        else:
            logger.info('Purge lock detected... skipping')
        return True

    @staticmethod
    def strip_unrelated(sceneid, opts):
        """
        Remove unnecessary keys from options
        :param sceneid: scene name
        :param opts: processing options
        :return: dict
        """
        opts = copy.deepcopy(opts)
        short = sensor.instance(sceneid).shortname
        sen_keys = sensor.SensorCONST.instances.keys()
        opts['products'] = opts[short]['products']

        for sen in sen_keys:
            if sen in opts:
                opts.pop(sen)

        return opts

    @staticmethod
    def production_whitelist():

        def getpid(slave):
            return slave.get('pid')

        def getip(instr):
            match = re.search("[0-9]{2,3}.[0-9]{1,2}.[0-9]{2}.[0-9]{1,3}", instr)
            return match.group(0)

        cache_key = 'prod_whitelist'
        prodlist  = cache.get(cache_key)
        mesos_url = config.url_for('mesos_master') # url.<mode>.mesos_master

        whitelist_additions = []
        if 'prod_whitelist_additions' in config.__dict__.keys():
            whitelist_additions = config.prod_whitelist_additions.replace("'","").split(",")

        if prodlist is None:
            logger.info("Regenerating production whitelist...")
            # timeout in 6 hours
            timeout = 60 * 60 * 6
            try:
                slaves   = requests.get(mesos_url + "/slaves", verify=False)
                pids = (getpid(s) for s in slaves.json()['slaves'])
                prodlist = [getip(pid) for pid in pids]
                prodlist.append('127.0.0.1')
                prodlist.append(socket.gethostbyname(socket.gethostname()))
                if whitelist_additions:
                    prodlist.extend(whitelist_additions)
            except BaseException as e:
                logger.exception('Could not access Mesos!')
            cache.set(cache_key, prodlist, timeout)

        return prodlist

    @staticmethod
    def reset_processing_status():
        """
        Resets all "queued/processing" scene states

        :return: bool
        """
        scenes = Scene.where({'status': ('tasked', 'scheduled', 'processing')})
        if scenes:
            Scene.bulk_update([s.id for s in scenes], {'status': 'submitted'})
            return True
        else:
            return False

    def handle_stuck_jobs(self, scenes):
        """
        Monitoring for long-overdue products, and auto-resubmission

        Note: This problem arises from lack of job scheduler grace when
              Mesos framework is closed.

        """
        if not len(scenes):
            return None

        logger.warning('Found {N} stuck tasks, retrying...'.format(N=len(scenes)))
        # Update scenes directly to oncache since they previously
        # went through the inventory check
        Scene.bulk_update([s.id for s in scenes], {'status': 'oncache',
                                                             'log_file_contents': '',
                                                             'note': '',
                                                             'retry_count': 0})

        return True
