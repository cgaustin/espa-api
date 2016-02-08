import api.domain.sensor as sn

"""
base = {'MOD09A1': {'inputs': 'MOD09A1.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MOD09GA': {'inputs': 'MOD09GA.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MOD09GQ': {'inputs': 'MOD09GQ.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MOD09Q1': {'inputs': 'MOD09Q1.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MYD09A1': {'inputs': 'MYD09A1.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MYD09GA': {'inputs': 'MYD09GA.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MYD09GQ': {'inputs': 'MYD09GQ.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MYD09Q1': {'inputs': 'MYD09Q1.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MOD13A1': {'inputs': 'MOD13A1.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MOD13A2': {'inputs': 'MOD13A2.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MOD13A3': {'inputs': 'MOD13A3.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MOD13Q1': {'inputs': 'MOD13Q1.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MYD13A1': {'inputs': 'MYD13A1.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MYD13A2': {'inputs': 'MYD13A2.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MYD13A3': {'inputs': 'MYD13A3.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'MYD13Q1': {'inputs': 'MYD13Q1.A2000072.h02v09.005.2008237032813',
                    'products': ['l1']},
        'tm4': {'inputs': 'LT42181092013069PFS00',
                'products': ['l1']},
        'tm5': {'inputs': 'LT52181092013069PFS00',
                'products': ['l1']},
        'etm7': {'inputs': 'LE72181092013069PFS00',
                 'products': ['l1']},
        'oli8': {'inputs': 'LO82181092013069PFS00',
                 'products': ['l1']},
        'olitirs8': {'inputs': 'LC82181092013069PFS00',
                     'products': ['l1']},
        'projection': {'lonlat': None},
        'image_extents': {'north': 0.0002695,
                          'south': 0,
                          'east': 0.0002695,
                          'west': 0,
                          'units': 'dd'},
        'format': 'gtiff',
        'resampling_method': 'cc',
        'resize': {'pixel_size': 0.0002695,
                   'pixel_size_units': 'dd'},
        'plot_statistics': True}"""


def build_base_order():
    base = {'projection': {'lonlat': None},
            'image_extents': {'north': 0.0002695,
                              'south': 0,
                              'east': 0.0002695,
                              'west': 0,
                              'units': 'dd'},
            'format': 'gtiff',
            'resampling_method': 'cc',
            'resize': {'pixel_size': 0.0002695,
                       'pixel_size_units': 'dd'},
            'plot_statistics': True}

    sensor_acqids = {'.A2000072.h02v09.005.2008237032813': (['MOD09A1', 'MOD09GA', 'MOD09GQ', 'MOD09Q1',
                                                             'MYD09A1', 'MYD09GA', 'MYD09GQ', 'MYD09Q1',
                                                             'MOD13A1', 'MOD13A2', 'MOD13A3', 'MOD13Q1',
                                                             'MYD13A1', 'MYD13A2', 'MYD13A3', 'MYD13Q1'],
                                                            ['MOD09A1', 'MOD09GA', 'MOD09GQ', 'MOD09Q1',
                                                             'MYD09A1', 'MYD09GA', 'MYD09GQ', 'MYD09Q1',
                                                             'MOD13A1', 'MOD13A2', 'MOD13A3', 'MOD13Q1',
                                                             'MYD13A1', 'MYD13A2', 'MYD13A3', 'MYD13Q1']),
                     '2181092013069PFS00': (['LT4', 'LT5', 'LE7', 'LO8', 'LC8'],
                                            ['tm4', 'tm5', 'etm7', 'oli8', 'olitirs8'])}

    for acq in sensor_acqids:
        for prefix, label in zip(sensor_acqids[acq][0], sensor_acqids[acq][1]):
            base[label] = {'inputs': ['{}{}'.format(prefix, acq)],
                           'products': sn.instance('{}{}'.format(prefix, acq)).products}

    return base


good_projs = {'aea': {'standard_parallel_1': 29.5,
                      'standard_parallel_2': 45.5,
                      'central_meridian': -96,
                      'latitude_of_origin': 23,
                      'false_easting': 0,
                      'false_northing': 0,
                      'datum': 'nad83'},
              'utm': {'zone': 33,
                      'zone_ns': 'south'},
              'lonlat': None,
              'sinu': {'central_meridian': 0,
                       'false_easting': 0,
                       'false_northing': 0},
              'ps': {'longitudinal_pole': 0,
                     'latitude_true_scale': 75}}


if __name__ == '__main__':
    print build_base_order()
