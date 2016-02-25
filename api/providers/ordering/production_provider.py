from api.domain import sensor
from api.domain.scene import Scene
from api.domain.order import Order
from api.domain.config import ApiConfig
from api.dbconnect import DBConnect, DBConnectException
from api.utils import api_cfg
from validate_email import validate_email
from api.providers.ordering import ProviderInterfaceV0
from api import errors
from api import lpdaac
from api import lta
from api import onlinecache
from api import emails
from api import nlaps

import yaml
import copy
import memcache
import datetime
import json

from cStringIO import StringIO

from api.api_logging import api_logger as logger

config = ApiConfig()
cache = memcache.Client(['127.0.0.1:11211'], debug=0)

class ProductionProviderException(Exception):
    pass

class ProductionProvider(object):

    def mark_product_complete(self, name=None, orderid=None, processing_loc=None,
                                completed_file_location=None, destination_cksum_file=None,
                                log_file_contents=None):

        order_id = Scene.get('order_id', name=name, orderid=orderid)
        order_source = Scene.get('order_source', name=name, orderid=orderid)
        base_url = config.url_for('distribution.cache')

        product_file_parts = completed_file_location.split('/')
        product_file = product_file_parts[len(product_file_parts) - 1]
        cksum_file_parts = destination_cksum_file.split('/')
        cksum_file = cksum_file_parts[len(cksum_file_parts) - 1]

        product_dload_url = ('%s/orders/%s/%s') % (base_url, orderid, product_file)
        cksum_download_url = ('%s/orders/%s/%s') % (base_url, orderid, cksum_file)

        sql_list = ["update ordering_scene set "]
        sql_list.append(" status = 'complete', ")
        sql_list.append(" processing_location = '{0}', ".format(processing_loc))
        sql_list.append(" product_distro_location = '{0}', ".format(completed_file_location))
        sql_list.append(" completion_date = {0}, ".format(datetime.datetime.now()))
        sql_list.append(" cksum_distro_location = '{0}', ".format(destination_cksum_file))
        sql_list.append(" log_file_contents = '{0}', ".format(log_file_contents))
        sql_list.append(" product_dload_url = '{0}', ".format(product_dload_url))
        sql_list.append(" cksum_download_url = '{0}' ".format(cksum_download_url))
        sql_list.append(" where name = '{0}' AND order_id = {1};".format(name, order_id))
        sql = " ".join(sql_list)

        if order_source == 'ee':
            # update EE
            ee_order_id = Scene.get('ee_order_id', name=name, orderid=orderid)
            ee_unit_id = Scene.get('ee_unit_id', name=name, orderid=orderid)
            lta.update_order_status(ee_order_id, ee_unit_id, 'C')

        try:
            with DBConnect(**api_cfg()) as db:
                db.execute(sql)
                db.commit()
        except DBConnectException, e:
            message = "DBConnect Exception ordering_provider set_product_unavailable sql: {0}"\
                        "\nmessage: {1}".format(sql, e.message)
            raise OrderingProviderException(message)

        return True

    def set_product_unavailable(self, name=None, orderid=None,
                                processing_loc=None, error=None, note=None):

        order_id = Scene.get('order_id', name=name, orderid=orderid)
        order_source = Scene.get('order_source', name=name, orderid=orderid)
        sql_list = ["update ordering_scene set "]
        sql_list.append(" status = 'unavailable', ")
        sql_list.append(" processing_location = '{0}', ".format(processing_loc))
        sql_list.append(" completion_date = {0}, ".format(datetime.datetime.now()))
        sql_list.append(" log_file_contents = '{0}', ".format(error))
        sql_list.append(" note = '{0}' ".format(note))
        sql_list.append(" where name = '{0}' AND order_id = {1};".format(name, order_id))
        sql = " ".join(sql_list)

        if order_source == 'ee':
            # update EE
            ee_order_id = Scene.get('ee_order_id', name=name, orderid=orderid)
            ee_unit_id = Scene.get('ee_unit_id', name=name, orderid=orderid)
            lta.update_order_status(ee_order_id, ee_unit_id, 'R')

        try:
            with DBConnect(**api_cfg()) as db:
                db.execute(sql)
                db.commit()
        except DBConnectException, e:
            message = "DBConnect Exception ordering_provider set_product_unavailable sql: {0}\nmessage: {1}".format(sql, e.message)
            raise OrderingProviderException(message)

        return True

    def set_products_unavailable(products, reason):
        '''Bulk updates products to unavailable status and updates EE if
        necessary.
        Keyword args:
        products - A list of models.Scene objects
        reason - The user facing reason the product was rejected
        '''
        for p in products:
            if not isinstance(p, Scene):
                raise TypeError()

        for p in products:
            p.update('status', 'unavailable')
            p.update('completion_date', datetime.datetime.now())
            p.update('note', reason)

            if p.order_attr('order_source') == 'ee':
                lta.update_order_status(p.order.ee_order_id, p.ee_unit_id, 'R')

    def update_status(self, name=None, orderid=None,
                        processing_loc=None, status=None):
        order_id = Scene.get('order_id', name=name, orderid=orderid)
        sql_list = ["update ordering_scene set "]
        comm_sep = ""
        if processing_loc:
            sql_list.append(" processing_location = '%s' " % processing_loc)
            comm_sep = ", "
        if status:
            sql_list.append(comm_sep)
            sql_list.append(" status = '%s'" % status)

        sql_list.append(" where name = '{0}' AND order_id = {1};".format(name, order_id))
        sql = " ".join(sql_list)

        try:
            with DBConnect(**api_cfg()) as db:
                db.execute(sql)
                db.commit()
        except DBConnectException, e:
            message = "DBConnect Exception ordering_provider update_status sql: {0}\nmessage: {1}".format(sql, e.message)
            raise OrderingProviderException(message)

        return True

    def update_product(self, action, name=None, orderid=None, processing_loc=None,
                        status=None, error=None, note=None,
                        completed_file_location=None,
                        cksum_file_location=None,
                        log_file_contents=None):

        permitted_actions = ('update_status', 'set_product_error',
                            'set_product_unavailable', 'mark_product_complete')

        if action not in permitted_actions:
            return {"msg": "{0} is not an accepted action for update_product".format(action)}

        if action == 'update_status':
            result = self.update_status(name=name, orderid=orderid,
                                        processing_loc=processing_loc, status=status)

        if action == 'set_product_error':
            result = self.set_product_error(name=name, orderid=orderid,
                                            processing_loc=processing_loc, error=error)

        if action == 'set_product_unavailable':
            result = self.set_product_unavailable(name=name, orderid=orderid,
                                                    processing_loc=processing_loc,
                                                    error=error, note=note)

        if action == 'mark_product_complete':
            result = self.mark_product_complete(name=name, orderid=orderid,
                                                processing_loc=processing_loc,
                                                completed_file_location=completed_file_location,
                                                destination_cksum_file=destination_cksum_file,
                                                log_file_contents=log_file_contents)

        return result

    def set_product_retry(self, name, orderid, processing_loc,
                        error, note, retry_after, retry_limit=None):
        """ Set a product to retry status """
        order_id = Scene.get('order_id', name=name, orderid=orderid)
        retry_count = Scene.get('retry_count', name=name, orderid=orderid)
        curr_limit = Scene.get('retry_limit', name=name, orderid=orderid)

        sql_list = ["update ordering_scene set "]
        comm_sep = ""
        if retry_limit is not None:
            comm_sep = ", "
            sql_list.append("retry_limit = {0}".format(retry_limit))
            curr_limit = retry_limit

        if retry_count + 1 <= curr_limit:
            sql_list.append(comm_sep)
            sql_list.append(" status = 'retry', ")
            sql_list.append(" retry_count = {0}, ".format(retry_count + 1))
            sql_list.append(" retry_after = {0}, ".format(retry_after))
            sql_list.append(" log_file_contents = '{0}', ".format(error))
            sql_list.append(" processing_loc = '{0}', ".format(processing_loc))
            sql_list.append(" note = '{0}'".format(note))
        else:
            raise OrderingProviderException("Exception Retry limit exceeded, name: {0}".format(name))

        sql_list.append(" where name = '{0}' AND order_id = {1};".format(name, order_id))
        sql = " ".join(sql_list)
        try:
            with DBConnect(**api_cfg()) as db:
                db.execute(sql)
                db.commit()
        except DBConnectException, e:
            message = "DBConnectException set_product_retry. message: {0}\nsql: {1}".format(e.message, sql)
            raise OrderingProviderException(message)

        return True

    def set_product_error(self, name=None, orderid=None,
                            processing_loc=None, error=None):

        sql_list = ["update ordering_scene set "]
        resolution = errors.resolve(error, name)
        order_id = Scene.get('order_id', name=name, orderid=orderid)

        if resolution is not None:
            if resolution.status == 'submitted':
                sql_list.append(" status = 'submitted', note = '' ")
            elif resolution.status == 'unavailable':
                now = datetime.datetime.now()
                sql_list.append(" status = 'unavailable', processing_location = '{0}', "\
                                "completion_date = {1}, log_file_contents = '{2}', "\
                                "note = '{3}' ".format(processing_loc, now, error, resolution.reason))

                ee_order_id = Scene.get('ee_order_id', name=name, orderid=orderid)
                ee_unit_id = Scene.get('ee_unit_id', name=name, orderid=orderid)
                lta.update_order_status(ee_order_id, ee_unit_id, 'R')

            elif resolution.status == 'retry':
                try:
                    set_product_retry(name, orderid, processing_loc, error,
                                        resolution.reason,
                                        resolution.extra['retry_after'],
                                        resolution.extra['retry_limit'])
                except Exception, e:
                    logger.debug("Exception setting {0} to retry:{1}".format(name, e))
                    sql_list.append(" status = 'error', processing_location = '{0}',"\
                                    " log_file_contents = {1} ".format(processing_loc, error))
        else:
            status = 'error'
            sql_list.append(" status = '{0}', processing_location = '{1}',"\
                            " log_file_contents = '{2}' ".format(status, processing_loc, error))

        sql_list.append(" where name = '{0}' AND order_id = {1};".format(name, order_id))
        sql = " ".join(sql_list)

        try:
            with DBConnect(**api_cfg()) as db:
                db.execute(sql)
                db.commit()
        except DBConnectException, e:
            message = "DBConnectException set_product_error. message: {0}\nsql: {1}".format(e.message, sql)
            raise OrderingProviderException(message)

        return True

    def get_products_to_process(self, record_limit=500,
                                for_user=None,
                                priority=None,
                                product_types=['landsat', 'modis'],
                                encode_urls=False):
        '''Find scenes that are oncache and return them as properly formatted
        json per the interface description between the web and processing tier'''

        logger.info('Retrieving products to process...')
        logger.warn('Record limit:{0}'.format(record_limit))
        logger.warn('Priority:{0}'.format(priority))
        logger.warn('For user:{0}'.format(for_user))
        logger.warn('Product types:{0}'.format(product_types))
        logger.warn('Encode urls:{0}'.format(encode_urls))

        buff = StringIO()
        buff.write('WITH order_queue AS ')
        buff.write('(SELECT u.email "email", count(name) "running" ')
        buff.write('FROM ordering_scene s ')
        buff.write('JOIN ordering_order o ON o.id = s.order_id ')
        buff.write('JOIN auth_user u ON u.id = o.user_id ')
        buff.write('WHERE ')
        buff.write('s.status in (\'queued\', \'processing\') ')
        buff.write('GROUP BY u.email) ')
        buff.write('SELECT ')
        buff.write('p.contactid, ')
        buff.write('s.name, ')
        buff.write('s.sensor_type, ')
        buff.write('o.orderid, ')
        buff.write('o.product_options, ')
        buff.write('o.priority, ')
        buff.write('o.order_date, ')
        buff.write('q.running ')
        buff.write('FROM ordering_scene s ')
        buff.write('JOIN ordering_order o ON o.id = s.order_id ')
        buff.write('JOIN auth_user u ON u.id = o.user_id ')
        buff.write('JOIN ordering_userprofile p ON u.id = p.user_id ')
        buff.write('LEFT JOIN order_queue q ON q.email = u.email ')
        buff.write('WHERE ')
        buff.write('o.status = \'ordered\' ')
        buff.write('AND s.status = \'oncache\' ')

        if product_types is not None and len(product_types) > 0:
            type_str = ','.join('\'{0}\''.format(x) for x in product_types)
            buff.write('AND s.sensor_type IN ({0}) '.format(type_str))

        if for_user is not None:
            buff.write('AND u.username = \'{0}\' '.format(for_user))

        if priority is not None:
            buff.write('AND o.priority = \'{0}\' '.format(priority))

        buff.write('ORDER BY q.running ASC NULLS FIRST, ')
        buff.write('o.order_date ASC LIMIT {0}'.format(record_limit))

        query = buff.getvalue()
        buff.close()
        logger.warn("QUERY:{0}".format(query))

        query_results = None

        with DBConnect(**api_cfg()) as db:
            db.select(query)

        query_results = db.fetcharr

        # Need the results reorganized by contact id so we can get dload urls from
        # ee in bulk by id.
        by_cid = {}
        for result in query_results:
            cid = result['contactid']
            # ['orderid', 'sensor_type', 'contactid', 'name', 'product_options']
            by_cid.setdefault(cid, []).append(result)

        #this will be returned to the caller
        results = []
        for cid in by_cid.keys():
            cid_items = by_cid[cid]

            landsat = [item['name'] for item in cid_items if item['sensor_type'] == 'landsat']
            logger.warn('Retrieving {0} landsat download urls for cid:{1}'
                         .format(len(landsat), cid))

            start = datetime.datetime.now()
            landsat_urls = lta.get_download_urls(landsat, cid)
            stop = datetime.datetime.now()
            interval = stop - start
            logger.warn('Retrieving download urls took {0} seconds'
                         .format(interval.seconds))
            logger.warn('Retrieved {0} landsat urls for cid:{1}'.format(len(landsat_urls), cid))

            modis = [item['name'] for item in cid_items if item['sensor_type'] == 'modis']
            modis_urls = lpdaac.get_download_urls(modis)

            logger.warn('Retrieved {0} urls for cid:{1}'.format(len(modis_urls), cid))

            for item in cid_items:
                dload_url = None
                if item['sensor_type'] == 'landsat':

                     # check to see if the product is still available

                    if ('status' in landsat_urls[item['name']] and
                            landsat_urls[item['name']]['status'] != 'available'):
                        try:
                            limit = config.settings['retry.retry_missing_l1.retries']
                            timeout = config.settings['retry.retry_missing_l1.timeout']
                            ts = datetime.datetime.now()
                            after = ts + datetime.timedelta(seconds=timeout)

                            logger.info('{0} for order {1} was oncache '
                                        'but now unavailable, reordering'
                                        .format(item['name'], item['orderid']))

                            set_product_retry(item['name'],
                                              item['orderid'],
                                              'get_products_to_process',
                                              'product was not available',
                                              'reorder missing level1 product',
                                              after, limit)
                        except Exception:

                            logger.info('Retry limit exceeded for {0} in '
                                        'order {1}... moving to error status.'
                                        .format(item['name'], item['orderid']))

                            set_product_error(item['name'], item['orderid'],
                                              'get_products_to_process',
                                              ('level1 product data '
                                               'not available after EE call '
                                               'marked product as available'))
                        continue

                    if 'download_url' in landsat_urls[item['name']]:
                        logger.info('download_url was in landsat_urls for {0}'.format(item['name']))
                        dload_url = landsat_urls[item['name']]['download_url']
                        if encode_urls:
                            dload_url = urllib.quote(dload_url, '')

                elif item['sensor_type'] == 'modis':
                    if 'download_url' in modis_urls[item['name']]:
                        dload_url = modis_urls[item['name']]['download_url']
                        if encode_urls:
                            dload_url = urllib.quote(dload_url, '')

                result = {
                    'orderid': item['orderid'],
                    'product_type': item['sensor_type'],
                    'scene': item['name'],
                    'priority': item['priority'],
                    'options': json.loads(item['product_options'])
                }

                if item['sensor_type'] == 'plot':
                    # no dload url for plot items, just append it
                    results.append(result)
                elif dload_url is not None:
                    result['download_url'] = dload_url
                    results.append(result)
                else:
                    logger.info('dload_url for {0} in order {0} '
                                'was None, skipping...'
                                .format(item['orderid'], item['name']))
        return results

    def load_ee_orders():
        ''' Loads all the available orders from lta into
        our database and updates their status
        '''

        #check to make sure this operation is enabled.  Bail if not
        enabled = config.settings["system.load_ee_orders_enabled"]
        if enabled.lower() != 'true':
            logger.info('system.load_ee_orders_enabled is disabled,'
                        'skipping load_ee_orders()')
            return

        # This returns a dict that contains a list of dicts{}
        # key:(order_num, email, contactid) = list({sceneid:, unit_num:})
        orders = lta.get_available_orders()

        # use this to cache calls to EE Registration Service username lookups
        local_cache = {}

        # Capture in our db
        for eeorder, email_addr, contactid in orders:
            # create the orderid based on the info from the eeorder
            order_id = Order.generate_ee_order_id(email_addr, eeorder)
            order = Order.where("orderid = '{0}'".format(order_id))

            if not order: # order is an empty list
                order = None
                # retrieve the username from the EE registration service
                # cache this call
                if contactid in local_cache:
                    username = local_cache[contactid]
                else:
                    username = lta.get_user_name(contactid)
                    local_cache[contactid] = username

                # now look the user up in our db. make sure the email we have on file is current
                # we'll want to put some caching in place here too
                user_params = ["username = '{0}'".format(username), "email = '{0}'".format(email_addr)]
                # User.where will create the user if they dont exist locally
                user = User.where(user_params)

                # * not sure yet why/where this is needed. commenting out till
                # * that is discovered. extends django models
                #try to retrieve the userprofile.  if it doesn't exist create
                #try:
                #    user.userprofile
                #except UserProfile.DoesNotExist:
                #    UserProfile(contactid=contactid, user=user).save()

                # We have a user now.  Now build the new Order since it
                # wasn't found.
                # TODO: This code should be housed in the models module.
                # TODO: This logic should not be visible at this level.
                order_dict = {}
                order_dict['orderid'] = order_id
                order_dict['user_id'] = user.id
                order_dict['order_type'] = 'level2_ondemand'
                order_dict['status'] = 'ordered'
                order_dict['note'] = 'EarthExplorer order id: %s' % eeorder
                order_dict['product_opts'] = json.dumps(Order.get_default_ee_options(),
                                                   sort_keys=True,
                                                   indent=4)
                order_dict['ee_order_id'] = eeorder
                order_dict['order_source'] = 'ee'
                order_dict['order_date'] = datetime.datetime.now()
                order_dict['priority'] = 'normal'
                order = Order.create(order_dict)


        for s in orders[eeorder, email_addr, contactid]:
            #go look for the scene by ee_unit_id.  This will stop
            #duplicate key update collisions

            scene = None
            try:
                scene_params = "order_id = {0} AND ee_unit_id = {1}".format(order.id, s['unit_num'])
                scene = Scene.where(scene_params)[0]

                if scene.status == 'complete':

                    success, msg, status =\
                        lta.update_order_status(eeorder, s['unit_num'], "C")

                    if not success:
                        log_msg = ("Error updating lta for "
                                   "[eeorder:%s ee_unit_num:%s "
                                   "scene name:%s order:%s to 'C' status")
                        log_msg = log_msg % (eeorder, s['unit_num'],
                                             scene.name, order.orderid)

                        logger.error(log_msg)

                        log_msg = ("Error detail: lta return message:%s "
                                   "lta return status code:%s")
                        log_msg = log_msg % (msg, status)

                        logger.error(log_msg)

                elif scene.status == 'unavailable':
                    success, msg, status =\
                        lta.update_order_status(eeorder, s['unit_num'], "R")

                    if not success:
                        log_msg = ("Error updating lta for "
                                   "[eeorder:%s ee_unit_num:%s "
                                   "scene name:%s order:%s to 'R' status")
                        log_msg = log_msg % (eeorder, s['unit_num'],
                                             scene.name, order.orderid)

                        logger.error(log_msg)

                        log_msg = ("Error detail: "
                                   "lta return message:%s  lta return "
                                   "status code:%s") % (msg, status)

                        logger.error(log_msg)
            except DBConnectException: #Scene does not exist
                product = None
                try:
                    product = sensor.instance(s['sceneid'])
                except Exception, e:
                    log_msg = ("Received product via EE that "
                               "is not implemented: %s" % s['sceneid'])
                    logger.debug(log_msg)
                    raise ProductionProviderException("Cant find sensor instance. {0}".format(log_msg))

                sensor_type = ""

                if isinstance(product, sensor.Landsat):
                    sensor_type = 'landsat'
                elif isinstance(product, sensor.Modis):
                    sensor_type = 'modis'

                scene_dict = {}

                scene_dict['name'] = product.product_id
                scene_dict['order_id'] = order.id
                scene_dict['status'] = 'submitted'
                scene_dict['sensor_type'] = sensor_type
                scene_dict['ee_unit_id'] = s['unit_num']
                # order_date isn't an column on the ordering_scene table
                # will leave commented out
                #scene_dict['order_date']= datetime.datetime.now()
                scene = Scene.create(scene_dict)

            # Update LTA
            success, msg, status =\
                lta.update_order_status(eeorder, s['unit_num'], "I")

            if not success:
                log_msg = ("Error updating lta for "
                           "[eeorder:%s ee_unit_num:%s scene "
                           "name:%s order:%s to 'I' status") % (eeorder,
                                                                s['unit_num'],
                                                                scene.name,
                                                                order.orderid)

                logger.error(log_msg)

                log_msg = ("Error detail: lta return message:%s  "
                           "lta return status code:%s") % (msg, status)

                logger.error(log_msg)



    def handle_retry_products(self):
        ''' handles all products in retry status '''
        now = datetime.datetime.now()
        filters = ["status = 'retry'",
                        "retry_after < '{0}'".format(now)]
        products = Scene.where(filters)

        if len(products) > 0:
            for product in products:
                product.update('status', 'submitted')
                product.update('note', '')

    def handle_onorder_landsat_products(self):
        ''' handles landsat products still on order '''

        filters = ["tram_order_id IS NOT NULL", "status = 'onorder'"]

        products = Scene.where(filters)
        product_tram_ids = [product.tram_order_id for product in products]

        rejected = []
        available = []

        for tid in product_tram_ids:
            order_status = lta.get_order_status(tid)

            # There are a variety of product statuses that come back from tram
            # on this call.  I is inprocess, Q is queued for the backend system,
            # D is duplicate, C is complete and R is rejected.  We are ignoring
            # all the statuses except for R and C because we don't care.
            # In the case of D (duplicates), when the first product completes, all
            # duplicates will also be marked C
            for unit in order_status['units']:
                if unit['unit_status'] == 'R':
                    rejected.append(unit['sceneid'])
                elif unit['unit_status'] == 'C':
                    available.append(unit['sceneid'])

        #Go find all the tram units that were rejected and mark them
        #unavailable in our database.  Note that we are not looking for
        #specific tram_order_id/sceneids as duplicate tram orders may have been
        #submitted and we want to bulk update all scenes that are onorder but
        #have been rejected
        if len(rejected) > 0:
            rejected_products = [p for p in products if p.name in rejected]
            set_products_unavailable(rejected_products,
                                     'Level 1 product could not be produced')

        #Now update everything that is now on cache
        filters = [
            "status = 'onorder'",
            "name in {0}".format(tuple(available))
        ]
        if len(available) > 0:
            products = Scene.where(filters)
            for product in products:
                product.update('status', 'oncache')
                product.update('note', '')

    def send_initial_emails(self):
        return emails.Emails().send_all_initial()

    def handle_submitted_landsat_products(self):
        ''' handles all submitted landsat products '''

        def mark_nlaps_unavailable():
            ''' inner function to support marking nlaps products unavailable '''

            logger.debug("In mark_nlaps_unavailable")

            #First things first... filter out all the nlaps scenes
            filters = "status = 'submitted' AND sensor_type = 'landsat'"

            logger.debug("Looking for submitted landsat products")

            landsat_products = Scene.where(filters)

            logger.debug("Found {0} submitted landsat products"
                         .format(len(landsat_products)))

            landsat_submitted = [l.name for l in landsat_products]

            logger.debug("Checking for TMA data in submitted landsat products")

            # find all the submitted products that are nlaps and reject them
            landsat_nlaps = nlaps.products_are_nlaps(landsat_submitted)

            landsat_submitted = None

            logger.debug("Found {0} landsat TMA products"
                .format(len(landsat_nlaps)))

            # bulk update the nlaps scenes
            if len(landsat_nlaps) > 0:

                _nlaps = [p for p in landsat_products if p.name in landsat_nlaps]

                landsat_nlaps = None

                set_products_unavailable(_nlaps, 'TMA data cannot be processed')

        def get_contactids_for_submitted_landsat_products():

            logger.info("Retrieving contact ids for submitted landsat products")

            scenes = Scene.where("status = 'submitted' AND sensor_type = 'landsat'")
            users = []
            for scene in scenes:
                user_parm = "id = {0}".format(scene.order_attr('user_id'))
                users.append(User.where(user_parm)[0])

            contact_ids = set([user.contactid for user in users])
            logger.info("Found contact ids:{0}".format(contact_ids))

            return contact_ids

        def update_landsat_product_status(contact_id):
            ''' updates the product status for all landsat products for the
            ee contact id '''

            logger.debug("Updating landsat product status")

            user = User.where("contactid = '{0}'".format(contactid))[0]

            product_list = Order.get_user_scenes(user.id, ["sensor_type = 'landsat' AND status = 'submitted'"])

            logger.debug("Ordering {0} scenes for contact:{1}"
                         .format(len(product_list), contact_id))

            results = lta.order_scenes(product_list, contact_id)

            logger.debug("Checking ordering results for contact:{0}"
                         .format(contact_id))

            if 'available' in results and len(results['available']) > 0:
                available_product_list = [product for product in product_list if product.name in results['available']]
                for product in available_product_list:
                    product.update('status', 'oncache')
                    product.update('note','')

            if 'ordered' in results and len(results['ordered']) > 0:
                ordered_product_list = [product for product in product_list if product.name in results['ordered']]
                for product in ordered_product_list:
                    product.update('status', 'onorder')
                    product.update('tram_order_id', results['lta_order_id'])
                    product.update('note', '')

            if 'invalid' in results and len(results['invalid']) > 0:
                #look to see if they are ee orders.  If true then update the
                #unit status

                invalid = [p for p in products if p.name in results['invalid']]

                set_products_unavailable(invalid, 'Not found in landsat archive')

        logger.info('Handling submitted landsat products...')

        #Here's the real logic for this handling submitted landsat products
        mark_nlaps_unavailable()

        for contact_id in get_contactids_for_submitted_landsat_products():
            try:
                logger.info("Updating landsat_product_status for {0}"
                            .format(contact_id))

                update_landsat_product_status(contact_id)

            except Exception, e:
                msg = ('Could not update_landsat_product_status for {0}\n'
                       'Exception:{1}'.format(contact_id, e))
                logger.exception(msg)

    def handle_submitted_modis_products(self):
        pass

    def handle_submitted_plot_products(self):
        pass

    def handle_submitted_products(self):
        ''' handles all submitted products in the system '''

        logger.info('Handling submitted products...')
        handle_submitted_landsat_products()
        handle_submitted_modis_products()
        handle_submitted_plot_products()

    def finalize_orders(self):
        pass

    def purge_orders(send_email=False):
        ''' Will move any orders older than X days to purged status and will also
        remove the files from disk'''

        days = config.settings['policy.purge_orders_after']
        logger.info('Using purge policy of {0} days'.format(days))

        cutoff = datetime.datetime.now() - datetime.timedelta(days=int(days))

        order_query = "status = 'complete' AND completion_date < '{0}'".format(cutoff)
        orders = Order.where(order_query)

        logger.info('Purging {0} orders from the active record.'
            .format(len(orders)))

        start_capacity = onlinecache.capacity()
        logger.info('Starting cache capacity:{0}'.format(start_capacity))

        for order in orders:
            try:
                # transaction is a django module
                #with transaction.atomic():
                order.update('status', 'purged')
                products = Scene.where("order_id = {0}".format(order.id))
                for product in products:
                    product.update('status', 'purged')
                    product.update('log_file_contents', '')
                    product.update('product_distro_location', '')
                    product.update('product_dload_url', '')
                    product.update('cksum_distro_location', '')
                    product.update('cksum_download_url', '')
                    product.update('job_name', '')

                # bulk update product status, delete unnecessary field data
                logger.info('Deleting {0} from online cache disk'
                   .format(order.orderid))

                onlinecache.delete(order.orderid)
            except onlinecache.OnlineCacheException:
                logger.debug('Could not delete {0} from the online cache'
                    .format(order.orderid))
            except Exception:
                logger.debug('Exception purging {0}'
                    .format(order.orderid))

        end_capacity = onlinecache.capacity()
        logger.info('Ending cache capacity:{0}'.format(end_capacity))

        if send_email is True:
            logger.info('Sending purge report')
            emails.send_purge_report(start_capacity, end_capacity, orders)

        return True

    def handle_orders(self):
        '''Logic handler for how we accept orders + products into the system'''
        send_initial_emails() #
        handle_onorder_landsat_products() #
        handle_retry_products() #
        load_ee_orders() #
        handle_submitted_products()
        finalize_orders()

        cache_key = 'orders_last_purged'
        result = cache.get(cache_key)

        # dont run this unless the cached lock has expired
        if result is None:
            logger.info('Purge lock expired... running')

            # first thing, populate the cached lock field
            timeout = int(config.settings['system.run_order_purge_every'])
            cache.set(cache_key, datetime.datetime.now(), timeout)

            #purge the orders from disk now
            purge_orders(send_email=True)  #
        else:
            logger.info('Purge lock detected... skipping')
        return True




# ??  queue_products          (order_name_tuple_list, processing_loc, job_name)


