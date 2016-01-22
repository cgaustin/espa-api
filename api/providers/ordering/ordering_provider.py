from api.domain import sensor
from api.dbconnect import DBConnect
from api.utils import get_cfg
from api.utils import is_empty
from api.utils import not_empty
import psycopg2.extras
import yaml
import re

class OrderingProvider(object):
    cfg = get_cfg()['config']
    cfg['cursor_factory'] = psycopg2.extras.DictCursor
    email_reg = '(\w+[.|\w])*@(\w+[.])*([a-zA-Z]*$)'

    @staticmethod
    def sensor_products(product_id):
        if isinstance(product_id, str):
            prod_list = product_id.split(",")
        else:
            prod_list = product_id

        return sensor.available_products(prod_list)

    @staticmethod
    def fetch_user(username):
        userlist = []
        with DBConnect(**OrderingProvider.cfg) as db:
            # username uniqueness enforced on auth_user table at database
            user_sql = "select id, username, email, is_staff, is_active, " \
                       "is_superuser from auth_user where username = %s;"
            db.select(user_sql, (username))
        if not_empty(db):
            userlist = db[0]

        return userlist


    def available_products(self, product_id, username):
        userlist = OrderingProvider.fetch_user(username)
        return_products = {}
        with open('api/domain/restricted.yaml') as f:
            restricted_list = yaml.load(f.read())

        if not_empty(userlist):
            # fetch all available products
            return_products = OrderingProvider.sensor_products(product_id)
            # Unless the user is staff, all possible products
            # are not available
            if userlist['is_staff'] == False:
                for prod in restricted_list['internal_only']:
                # ['swe', 'lst'] 1/22/16 
                    for sensor_type in return_products.keys():
                        if prod in return_products[sensor_type]['outputs']:
                            return_products[sensor_type]['outputs'].remove(prod)

        return return_products


    def fetch_user_orders(self, uid):
        id_type = 'email' if re.search(OrderingProvider.email_reg, uid) else 'username'
        order_list = []
        out_dict = {}
        user_ids = []

        with DBConnect(**OrderingProvider.cfg) as db:
            user_sql = "select id, username, email from auth_user where "
            user_sql += "email = %s;" if id_type == 'email' else "username = %s;"
            db.select(user_sql, (uid))
            # username uniqueness enforced on the db
            # not the case for emails though
            if not_empty(db):
                user_ids = [db[ind][0] for ind, val in enumerate(db)]

            if not_empty(user_ids):
                user_tup = tuple([str(idv) for idv in user_ids])
                sql = "select orderid from ordering_order where user_id in {};".format(user_tup)
                sql = sql.replace(",)",")")
                db.select(sql)
                if not_empty(db):
                    order_list = [item[0] for item in db]

        out_dict["orders"] = order_list
        return out_dict


    def fetch_order(self, ordernum):
        sql = "select * from ordering_order where orderid = %s;"
        out_dict = {}
        opts_dict = {}
        scrub_keys = ['initial_email_sent', 'completion_email_sent', 'id', 'user_id', 
			'ee_order_id', 'email']

        with DBConnect(**OrderingProvider.cfg) as db:
            db.select(sql, (ordernum))
            if not_empty(db):
                for key, val in db[0].iteritems():
			out_dict[key] = val
                opts_str = db[0]['product_options']
                opts_str = opts_str.replace("\n","")
		opts_dict = yaml.load(opts_str)
		out_dict['product_options'] = opts_dict

        for k in scrub_keys:
            if k in out_dict.keys():
                out_dict.pop(k)

        return out_dict


    def place_order(self, username, order):
        pass


    def list_orders(self, username_or_email):
        pass

    def view_order(self, orderid):
        pass

    def order_status(self, orderid):
        pass

    def item_status(self, orderid, itemid='ALL'):
        """

        :rtype: str
        """
        pass
