def get_user_name(arg1):
    return arg1

# product_list is type list, contact_id is type str
# needs to return a dict of dicts
def get_download_urls(product_list, contact_id):
    response = {}
    for item in product_list:
        item_dict = {'lta_prod_code': 'T272'}
        item_dict['sensor'] = 'LANDSAT_8'
        item_dict['status'] = 'available'
        item_dict['download_url'] = 'http://one_time_use.tar.gz'
        response[item] = item_dict
    return response


def update_order_status(ee_order_id, ee_unit_id, something):
    return True


def get_available_orders():
    """
    Needs to return:

    response[ordernumber, email, contactid] = [
            {'sceneid':orderingId, 'unit_num':unitNbr},
            {...}
        ]
    """
    ret = {}
    ret[(123, 'klsmith@usgs.gov', 418781)] = [{'sceneid': 'LE70900652008327EDC00',
                                               'unit_num': 789},
                                              {'sceneid': 'LE70900652008327EDC00',
                                               'unit_num': 780}]
    ret[(124, 'klsmith@usgs.gov', 418781)] = [{'sceneid': 'LE70900652008327EDC00',
                                               'unit_num': 780},
                                              {'sceneid': 'LE70900652008327EDC00',
                                               'unit_num': 799}]
    return ret
