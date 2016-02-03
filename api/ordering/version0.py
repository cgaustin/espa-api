"""API interface for placing and viewing orders.

   Any methods exposed through this interface are intended to be consumed by
   end users (publicly). The module should be the pure interface for the api
   functions.  Don't import or include any implementation specific items here,
   just logic.  Implementations are touched through the registry.
"""
import sys
from api.api_logging import api_logger as logger

class API(object):
    def __init__(self, providers=None):
        if providers is not None:
            self.providers = providers()
        else:
            from api.ordering.providers import DefaultProviders
            self.providers = DefaultProviders()

        self.ordering = self.providers.ordering
        self.inventory = self.providers.inventory
        self.validation = self.providers.validation
        self.metrics = self.providers.metrics

    def api_versions(self):
        """
        Provides list of available api versions

        Returns:
            dict: of api versions and a description

        Example:
            {
                "0":
                    "description": "Demo access points for development",
                }
            }
        """
        return self.providers.api_versions

    def available_products(self, product_id, username):
        """
        Provides list of available products given
        a scene id.

        Args:
            product_id (str): the scene id to retrieve list of availabe products for.

        Returns:
            dict: of available products

        Example:
            {
              "etm": {
                  "inputs": [
                        "LE70290302003123EDC00"
                            ],
                            "outputs": [
                                "etm_sr",
                                "etm_toa",
                                "etm_l1",
                                "source",
                                "source_metadata"
                              ]
                            },
                            "not_implemented": [
                              "bad scene id"
                            ],
                    }
        """
        try:
            response = self.ordering.available_products(product_id, username)
        except:
            exc_type, exc_val, exc_trace = sys.exc_info()
            msg = "ERR version0 available_prods_get arg: {0}".format(product_id)
            msg += "exception type: {0}   value: {1}   trace:{2}".format(exc_type, exc_val, exc_trace)
            logger.debug(msg)
            response = {"msg": "there's been a problem retrieving your information. admins have been notified"}

        return response

    def fetch_user_orders(self, user_id):
        """ Return orders given a user id

        Args:
            user_id (str): The email or username for the user who placed the order.

        Returns:
            dict: of orders with list of order ids
        """
        try:
            response = self.ordering.fetch_user_orders(user_id)
        except:
            exc_type, exc_val, exc_trace = sys.exc_info()
            msg = "ERR version0 fetch_user_orders arg: {0}".format(user_id)
            msg += "exception type: {0}   value: {1}   trace:{2}".format(exc_type, exc_val, exc_trace)
            logger.debug(msg)
            response = {"msg": "there's been a problem retrieving your information. admins have been notified"}

        return response

    def fetch_order(self, ordernum):
        """ Returns details of a submitted order

        Args:
            ordernum (str): the order id of a submitted order

        Returns:
            dict: of order details
        """
        try:
            response = self.ordering.fetch_order(ordernum)
        except:
            exc_type, exc_val, exc_trace = sys.exc_info()
            msg = "ERR version0 fetch_order arg: {0}".format(ordernum)
            msg += "exception type: {0}   value: {1}   trace:{2}".format(exc_type, exc_val, exc_trace)
            logger.debug(msg)
            response = {"msg": "there's been a problem retrieving your information. admins have been notified"}

        return response

    def place_order(self, order):
        """Enters a new order into the system.

        Args:
            :keyword order (api.domain.order.Order): The order to be entered into the system

        Returns:
            str: The generated order id

        Raises:
            api.exceptions.ValidationException: Error occurred validating params
            api.exceptions.InventoryException: Items were not found/unavailable
        """
        try:
            # perform validation, raises ValidationException
            self.validation(order)
            # performs inventory check, raises InventoryException
            self.inventory.check(order)
            # track metrics
            self.metrics.collect(order)
            # capture the order
            response = self.ordering.place_order(order)
        except:
            exc_type, exc_val, exc_trace = sys.exc_info()
            msg = "ERR version0 place_order arg: {0}".format(order)
            msg += "exception type: {0}   value: {1}   trace:{2}".format(exc_type, exc_val, exc_trace)
            logger.debug(msg)
            response = {"msg": "there's been a problem placing your order. admins have been notified"}

        return response

    def list_orders(self, username_or_email):
        """Returns all the orders for the user

        Args:
            username_or_email (str): Username or email address of user

        Returns:
            list: A list of all the users orders (order ids).  May be zero length
        """
        try:
            response = self.ordering.list_orders(username_or_email)
        except:
            exc_type, exc_val, exc_trace = sys.exc_info()
            msg = "ERR version0 list_order arg: {0}".format(username_or_email)
            msg += "exception type: {0}   value: {1}   trace:{2}".format(exc_type, exc_val, exc_trace)
            logger.debug(msg)
            response = {"msg": "there's been an issue retrieving your information. admins have been notified"}

        return response

    def view_order(self, orderid):
        """Show details for a user order

        Args:
            orderid (str): The orderid to view

        Returns:
            api.domain.order.Order: Same information as when placing the order

        Raises:
            OrderNotFound:
        """
        try:
            response = self.ordering.view_order(orderid)
        except:
            exc_type, exc_val, exc_trace = sys.exc_info()
            msg = "ERR version0 view_order arg: {0}".format(orderid)
            msg += "exception type: {0}   value: {1}   trace:{2}".format(exc_type, exc_val, exc_trace)
            logger.debug(msg)
            response = {"msg": "there's been an issue retrieving your information. admins have been notified"}

        return response

    def order_status(self, orderid):
        """Shows an order status

        Orders contain additional information such as date ordered, date completed,
        current status and so on.

        Args:
            orderid (str): id of the order

        Raises:
            OrderNotFound if the order did not exist
        """
        try:
            response = self.ordering.order_status(orderid)
        except:
            exc_type, exc_val, exc_trace = sys.exc_info()
            msg = "ERR version0 order_status arg: {0}".format(orderid)
            msg += "exception type: {0}   value: {1}   trace:{2}".format(exc_type, exc_val, exc_trace)
            logger.debug(msg)
            response = {"msg": "there's been an issue retrieving your information. admins have been notified"}

        return response

    def item_status(self, orderid, itemid='ALL'):
        """Shows an individual item status

        Args:
            orderid (str): id of the order
            itemid (str): id of the item.  If ALL is specified, a list of status
                          for all items in the order will be returned.

        Returns:
            list: list of dictionaries with status, completion_time and note

        Raises:
            ItemNotFound if the item did not exist
        """
        try:
            response = self.ordering.item_status(orderid, itemid)
        except:
            exc_type, exc_val, exc_trace = sys.exc_info()
            msg = "ERR version0 item_status arg: {0}".format(itemid)
            msg += "exception type: {0}   value: {1}   trace:{2}".format(exc_type, exc_val, exc_trace)
            logger.debug(msg)
            response = {"msg": "there's been an issue retrieving your information. admins have been notified"}

        return response


