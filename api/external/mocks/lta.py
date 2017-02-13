import xml.etree.ElementTree as xml

from api.util import chunkify


def return_update_order_resp(*args, **kwargs):
    class foo(object):
        def success(self):
            return True
    return foo()


def get_user_name(arg1):
    return 'klsmith@usgs.gov'


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
    return True, True, True


def update_order_status_fail(ee_order_id, ee_unit_id, something):
    raise Exception('lta comms failed')


def order_scenes(product_list, contact_id):
    chunked_list = chunkify(product_list, 3)
    results = dict()
    results["available"] = [p for p in chunked_list[0]]
    results["ordered"] = [p for p in chunked_list[1]]
    results["invalid"] = [p for p in chunked_list[2]]
    results["lta_order_id"] = "tramorderid1"
    return results


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


def get_available_orders_partial(partial=False):
    ret = {}
    if partial:
        ret[(125, 'klsmith@usgs.gov', 418781)] = [{'sceneid': 'LE70900652008327EDC00',
                                                   'unit_num': 789}]
    else:
        ret[(125, 'klsmith@usgs.gov', 418781)] = [{'sceneid': 'LE70900652008327EDC00',
                                                   'unit_num': 789},
                                                  {'sceneid': 'LT50900652008327EDC00',
                                                   'unit_num': 780}]

    return ret


def sample_tram_order_ids():
    return '0611512239617', '0611512239618', '0611512239619'


def sample_scene_names():
    return 'LC81370432014073LGN00', 'LC81390422014071LGN00', 'LC81370422014073LGN00'


def get_order_status(tramid):
    response = None
    if tramid == sample_tram_order_ids()[0]:
        response = {'units': [{'sceneid':sample_scene_names()[0], 'unit_status': 'R'}]}
    elif tramid == sample_tram_order_ids()[1]:
        response = {'units': [{'sceneid':sample_scene_names()[1], 'unit_status': 'C'}]}
    elif tramid == sample_tram_order_ids()[2]:
        response = {'units': [{'sceneid':sample_scene_names()[2], 'unit_status': 'R'}]}
    else:
        response = {'units': [{'sceneid': sample_scene_names()[0], 'unit_status': 'C'}]}
    return response


class MockRequestsResponse(object):
    def close(self):
        pass
    ok = True
    status_code = 200
    content = b''
    text = r''


def get_verify_scenes_response(url, data, headers):
    response = MockRequestsResponse()
    response.content = ('<?xml version="1.0" encoding="UTF-8"?>\n<validSceneList xmlns="http://earthexplorer.usgs.gov/s'
                        'chema/validSceneList" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation'
                        '="http://earthexplorer.usgs.gov/schema/validSceneList https://eedevmast.cr.usgs.gov/OrderWrapp'
                        'erServicedevmast/validSceneList.xsd">\n')

    root = xml.fromstring(data)
    scenes = root.getchildren()
    for s in list(scenes):
        response.content += ('<sceneId  sensor="{s}" valid="true">{t}</sceneId>\n'
                             .format(s=s.attrib['sensor'], t=s.text))

    response.content += '</validSceneList>\n'
    response.ok = True
    response.status_code = 200
    response.reason = 'OK'
    return response


def get_order_scenes_response_main(url, data, headers=None):
    if 'submitOrder' in url:
        return get_order_scenes_response(data)


def get_order_scenes_response(data):
    response = MockRequestsResponse()
    response.content = ('<?xml version="1.0" encoding="UTF-8"?>\n<orderStatus xmlns="http://earthexplorer.usgs.gov/sche'
                        'ma/orderStatus" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation'
                        '="http://earthexplorer.usgs.gov/schema/orderStatus https://eedevmast.cr.usgs.gov/OrderWrapp'
                        'erServicedevmast/orderStatus.xsd">\n')

    root = xml.fromstring(data)
    response_namespace = 'https://earthexplorer.usgs.gov/schema/orderParameters'
    scenes = root.findall("ee:scene", namespaces={'ee': response_namespace})
    for s in list(scenes):
        response.content += ('<scene>\n')
        name = s[0].text
        response.content += ('<sceneId>{}</sceneId>\n'.format(name))
        prodcode = 'Txxx'
        response.content += ('<prodCode>{}</prodCode>\n'.format(prodcode))
        sensor = s[1].text
        response.content += ('<sensor>{}</sensor>\n'.format(sensor))
        status = 'ordered'
        orderno = '0621405213419'
        response.content += ('<status>{}</status>\n'.format(status))
        response.content += ('<orderNumber>{}</orderNumber>\n'.format(orderno))
        response.content += ('</scene>\n')

    response.content += '</orderStatus>\n'
    response.ok = True
    response.status_code = 200
    response.reason = 'OK'
    return response


class get_available_orders_response(object):
    # resp = self.client.service.getAvailableOrders("ESPA")
    def __init__(self, *args, **kwargs):
        pass

    class service(object):
        def getAvailableOrders(self, sensor):
            self.units = []
            return self

    service = service()