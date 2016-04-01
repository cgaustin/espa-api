"""API interface for placing and viewing orders.

   Any methods exposed through this interface are intended to be consumed by
   end users (publicly). The module should be the pure interface for the api
   functions.  Don't import or include any implementation specific items here,
   just logic.  Implementations are touched through the registry.
"""
import traceback
from api.system.logger import ilogger as logger
from api.domain import default_error_message
from api import ValidationException, InventoryException

import json


class API(object):
    def __init__(self, providers=None):
        if providers is not None:
            self.providers = providers()
        else:
            from api.interfaces.providers import DefaultProviders
            self.providers = DefaultProviders()

        self.ordering = self.providers.ordering
        self.inventory = self.providers.inventory
        self.validation = self.providers.validation
        self.metrics = self.providers.metrics
        self.production = self.providers.production
        self.configuration = self.providers.configuration
        self.reporting = self.providers.reporting

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
            logger.debug("ERR version0 available_prods_get product_id: {0} "
                         "username: {1}\nexception {2}".format(product_id, username,
                                                               traceback.format_exc()))
            response = default_error_message

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
            logger.debug("ERR version0 fetch_user_orders arg: {0}\nexception {1}".format(user_id, traceback.format_exc()))
            response = default_error_message

        return response


    def fetch_user_orders_ext(self, user_id):
        """ Return orders and product details given a user id

        Args:
            user_id (str): The email or username for the user who placed the order.

        Returns:
            list: of dictionaries with keys for orders and product details
        """
        try:
            response = self.ordering.fetch_user_orders_ext(user_id)
        except:
            logger.debug("ERR version0 fetch_user_orders arg: {0}\nexception {1}".format(user_id, traceback.format_exc()))
            response = default_error_message

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
            logger.debug("ERR version0 fetch_order arg: {0}\nexception {1}".format(ordernum, traceback.format_exc()))
            response = default_error_message

        return response

    def place_order(self, order, user):
        """Enters a new order into the system.

        Args:
            :keyword order (api.domain.order.Order): The order to be entered into the system

        Returns:
            str: The generated order id

        Raises:
            api.api_exceptions.ValidationException: Error occurred validating params
            api.api_exceptions.InventoryException: Items were not found/unavailable
        """
        try:
            # perform validation, raises ValidationException
            order = self.validation.validate(order, user.username)
            # performs inventory check, raises InventoryException
            self.inventory.check(order)
            # track metrics
            self.metrics.collect(order)
            # capture the order
            response = self.ordering.place_order(order, user)
        except ValidationException as e:
            logger.info('Invalid order received: {0}\nresponse {1}'.format(order, e.response))
            # Need to format the string repr of the exception for end user consumption
            response = e.response
        except InventoryException as e:
            logger.info('Requested inputs not available: {0}\nresponse {1}'.format(order, e.response))
            response = e.response
        except:
            logger.debug("ERR version0 place_order arg: {0}\nexception {1}".format(order, traceback.format_exc()))
            response = default_error_message

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
            logger.debug("ERR version0 order_status arg: {0}\nexception {1}".format(orderid, traceback.format_exc()))
            response = default_error_message

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
            logger.debug("ERR version0 item_status itemid {0}  orderid: {1}\nexception {2}".format(itemid, orderid, traceback.format_exc()))
            response = default_error_message

        return response

    def get_report(self, name):
        """
        retrieve a named report
        :param name:
        :return: OrderedDict
        """
        try:
            response = str(self.reporting.run(name))
        except:
            logger.debug("ERR version0 get_report name {0}\ntraceback {1}".format(name, traceback.format_exc()))
            response = default_error_message

        return response

    def available_reports(self):
        """
        returns list of available reports
        :return: List
        """
        try:
            response = self.reporting.listing()

        except:
            logger.debug("ERR version0 available_reports traceback {0}".format(traceback.format_exc()))
            response = default_error_message

        return response

    def get_system_status(self):
        """
        retrieve the system status message
        :return: str
        """
        try:
            response = self.ordering.get_system_status()
        except:
            logger.debug("ERR version0 get_system_status. traceback {0}".format(traceback.format_exc()))
            response = default_error_message

        return response

    def available_stats(self):
        """
        returns list of available statistics
        :return: list
        """
        try:
            response = self.reporting.stat_list()
        except:
            logger.debug("ERR version0 available_stats traceback {0}".format(traceback.format_exc()))
            response = default_error_message

        return response

    def get_stat(self, name):
        """
        retrieve requested statistic value
        :return: long
        """
        try:
            response = self.reporting.get_stat(name)
        except:
            logger.debug("ERR version0 get_stat name: {0}, traceback: {1}".format(name, traceback.format_exc()))
            response = default_error_message
        return response