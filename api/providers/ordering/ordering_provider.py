import datetime

from api.domain import sensor
from api.domain.order import Order
from api.util.dbconnect import db_instance
from validate_email import validate_email
from api.providers.ordering import ProviderInterfaceV0

import yaml
import copy
import memcache

cache = memcache.Client(['127.0.0.1:11211'], debug=0)


class OrderingProviderException(Exception):
    pass


class OrderingProvider(ProviderInterfaceV0):
    @staticmethod
    def sensor_products(product_id):
        # coming from uwsgi, product_id is unicode
        if isinstance(product_id, basestring):
            prod_list = product_id.split(",")
        else:
            prod_list = product_id

        return sensor.available_products(prod_list)

    @staticmethod
    def fetch_user(username):
        with db_instance() as db:
            # username uniqueness enforced on auth_user table at database
            user_sql = "select id, username, email, is_staff, is_active, " \
                       "is_superuser from auth_user where username = %s;"
            db.select(user_sql, (username))

        return db[0]

    def available_products(self, product_id, username):
        userlist = OrderingProvider.fetch_user(username)
        pub_prods = OrderingProvider.sensor_products(product_id)
        return_prods = {}
        if userlist['is_staff']:
            return_prods = pub_prods
        else:
            with open('api/domain/restricted.yaml') as f:
                restricted = yaml.load(f.read())
            for sensor_type in pub_prods:
                sensor_restr = restricted.get(sensor_type, [])
                sensor_restr.extend(restricted.get('all'))

                if sensor_type == 'not_implemented':
                    continue

                for restr in sensor_restr:
                    if restr in pub_prods[sensor_type]['outputs']:
                        pub_prods[sensor_type]['outputs'].remove(restr)

        return return_prods

    def fetch_user_orders(self, uid):
        id_type = 'email' if validate_email(uid) else 'username'
        order_list = []
        out_dict = {}
        user_ids = []

        with db_instance() as db:
            user_sql = "select id, username, email from auth_user where "
            user_sql += "email = %s;" if id_type == 'email' else "username = %s;"
            db.select(user_sql, (uid))
            # username uniqueness enforced on the db
            # not the case for emails though
            if db:
                user_ids = [db[ind][0] for ind, val in enumerate(db)]

            if user_ids:
                user_tup = tuple([str(idv) for idv in user_ids])
                sql = "select orderid from ordering_order where user_id in {};".format(user_tup)
                sql = sql.replace(",)", ")")
                db.select(sql)
                if db:
                    order_list = [item[0] for item in db]

        out_dict["orders"] = order_list
        return out_dict

    def fetch_order(self, ordernum):
        sql = "select * from ordering_order where orderid = %s;"
        out_dict = {}
        opts_dict = {}
        scrub_keys = ['initial_email_sent', 'completion_email_sent', 'id', 'user_id',
                      'ee_order_id', 'email']

        with db_instance() as db:
            db.select(sql, (str(ordernum)))
            if db:
                for key, val in db[0].iteritems():
                    out_dict[key] = val
                opts_str = db[0]['product_options']
                opts_str = opts_str.replace("\n", "")
                opts_dict = yaml.load(opts_str)
                out_dict['product_options'] = opts_dict

        for k in scrub_keys:
            if k in out_dict.keys():
                out_dict.pop(k)

        return out_dict

    def place_order(self, new_order, user):
        """
        Build an order dictionary to be place into the system

        :param new_order: dictionary representation of the order received
        :param user: user information associated with the order
        :return: orderid to be used for tracking
        """

        order_dict = {}
        order_dict['orderid'] = Order.generate_order_id(user.email)
        order_dict['user_id'] = user.id
        order_dict['order_type'] = 'level2_ondemand'
        order_dict['status'] = 'ordered'
        order_dict['product_opts'] = new_order
        order_dict['ee_order_id'] = ''
        order_dict['order_source'] = 'espa'
        order_dict['order_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        order_dict['priority'] = 'normal'
        order_dict['note'] = ''
        order_dict['email'] = user.email
        order_dict['product_options'] = ''

        result = Order.create(order_dict)
        return result.orderid

    def order_status(self, orderid):
        sql = "select orderid, status from ordering_order where orderid = %s;"
        response = {}
        with db_instance() as db:
            db.select(sql, str(orderid))
            if db:
                for i in ['orderid', 'status']:
                    response[i] = db[0][i]
            else:
                response['msg'] = 'sorry, no orders matched orderid %s' % orderid

        return response

    def item_status(self, orderid, itemid='ALL'):
        response = {}
        sql = "select oo.orderid, os.name, os.status, os.completion_date, os.note " \
              "from ordering_order oo left join ordering_scene os on oo.id = " \
              "os.order_id where oo.orderid = %s"
        if itemid is not "ALL":
            argtup = (orderid, itemid)
            sql += " AND os.name = %s;"
        else:
            argtup = (str(orderid))
            sql += ";"

        with db_instance() as db:
            db.select(sql, argtup)
            items = [_ for _ in db.fetcharr]

        if items:
            id = items[0]['orderid']
            response['orderid'] = {id: []}
            for item in items:
                ts = ''
                try:
                    # Not always present
                    ts = item['completion_date'].strftime('%m-%d-%Y %H:%M:%S')
                except:
                    pass

                i = {'name': item['name'],
                     'status': item['status'],
                     'completion_date': ts,
                     'note': item['note']}
                response['orderid'][id].append(i)
        else:
            response['msg'] = 'sorry, no items matched orderid %s , itemid %s' % (orderid, itemid)

        return response
