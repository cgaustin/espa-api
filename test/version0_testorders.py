import copy
import collections

import api.domain.sensor as sn


good_test_projections = {'aea': {'standard_parallel_1': 29.5,
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


def build_base_order():
    """
    Builds the following dictionary (with the products filled out from sensor.py):

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


class InvalidOrders(object):
    def __init__(self, valid_order, schema, alt_fields=None):
        self.valid_order = valid_order
        self.schema = schema
        self.alt_fields = alt_fields

        self.invalid_list = []
        self.invalid_list.extend(self.build_invalid_list())

    def __iter__(self):
        return iter(self.invalid_list)

    def build_invalid_list(self, path=None):
        if not path:
            path = tuple()

        results = []

        sch_base = self.schema
        base = self.valid_order
        for key in path:
            sch_base = sch_base['properties'][key]
            base = base[key]

        for key, val in base.items():
            constraints = sch_base['properties'][key]
            mapping = path + (key,)

            for constr_type, constr in constraints.items():
                invalidatorname = 'invalidate_' + constr_type

                try:
                    invalidator = getattr(self, invalidatorname, None)
                except:
                    raise Exception('{} has no associated testing'.format(constr_type))

                results.extend(invalidator(constr, mapping))

            if constraints['type'] == 'object':
                results.extend(self.build_invalid_list(mapping))

        return results

    def invalidate_type(self, val_type, mapping):
        """
        Change the variable type
        """
        order = self.valid_order.copy()
        results = []
        test_vals = []

        if val_type == 'string':
            test_vals.append(9999)

        elif val_type == 'integer':
            test_vals.append('NOT A NUMBER')
            test_vals.append(1.1)

        elif val_type == 'number':
            test_vals.append('NOT A NUMBER')

        elif val_type == 'boolean':
            test_vals.append('NOT A BOOL')
            test_vals.append(2)
            test_vals.append(-1)

        elif val_type == 'object':
            test_vals.append('NOT A DICTIONARY')

        elif val_type == 'array':
            test_vals.append('NOT A LIST')

        elif val_type == 'null':
            test_vals.append('NOT NONE')

        elif val_type == 'any':
            pass

        else:
            raise Exception('{} constraint not accounted for in testing'.format(val_type))

        for val in test_vals:
            upd = self.build_update_dict(mapping, val)
            results.append((self.update_dict(order, upd), 'type', mapping))

        return results

    def invalidate_properties(self, val_type, mapping):
        """
        This is a pass through key in the schema
        only affects orders in the validation processing
        not whether an order is valid or invalid
        """
        # order = self.valid_order.copy()
        # results = []

        return []

    def invalidate_dependencies(self, dependency, mapping):
        """
        Remove dependencies, one at a time
        """
        order = self.valid_order.copy()
        results = []

        for dep in dependency:
            path = mapping[:-1] + (dep,)
            results.append((self.delete_key_loc(order, path), 'dependencies', mapping))

        return results

    def invalidate_enum(self, enums, mapping):
        """
        Add a value not covered in the enum list
        """
        order = self.valid_order.copy()
        results = []

        inv = 'NOT VALID ENUM'

        upd = self.build_update_dict(mapping, inv)
        results.append((self.update_dict(order, upd), 'enum', mapping))
        return results

    def invalidate_required(self, req, mapping):
        """
        If the value is required, remove it
        """
        order = self.valid_order.copy()
        results = []

        if req:
            results.append((self.delete_key_loc(order, mapping), 'required', mapping))

        return results

    def invalidate_maximum(self, max_val, mapping):
        """
        Add one to the maximum allowed value
        """
        order = self.valid_order.copy()
        results = []

        upd = self.build_update_dict(mapping, max_val + 1)
        results.append((self.update_dict(order, upd), 'maximum', mapping))
        return results

    def invalidate_minimum(self, min_val, mapping):
        """
        Subtract one from the minimum allowed value
        """
        order = self.valid_order.copy()
        results = []

        upd = self.build_update_dict(mapping, min_val + 1)
        results.append((self.update_dict(order, upd), 'minimum', mapping))
        return results

    def invalidate_uniqueItems(self, unique, mapping):
        """
        Add a duplicate entry into the list
        """
        order = self.valid_order.copy()
        results = []

        if unique:
            base = order

            for key in mapping:
                base = base[key]

            base.append(base[0])

            upd = self.build_update_dict(mapping, base)
            results.append((self.update_dict(order, upd), 'uniqueItems', mapping))

        return results

    def invalidate_items(self, val_type, mapping):
        order = self.valid_order.copy()
        results = []

        return results

    def invalidate_minItems(self, val_type, mapping):
        return []

    def invalidate_maxItems(self, val_type, mapping):
        return []

    def invalidate_single_obj(self, val_type, mapping):
        order = self.valid_order.copy()
        results = []
        # Needs to append a valid structure
        # Mainly pertains to the projection structure

        return results

    def invalidate_enum_keys(self, keys, mapping):
        """
        Append a dictionary with a key that is not in the
        enum list
        """
        order = self.valid_order.copy()
        results = []

        inv_key = {'INVALID KEY': None}

        upd = self.build_update_dict(mapping, inv_key)
        results.append((self.update_dict(order, upd), 'enum_keys', mapping))
        return results

    def invalidate_extents(self, val_type, mapping):
        order = self.valid_order.copy()
        results = []

        return results

    def update_dict(self, old, new):
        """
        Update a nested dictionary value following along a defined key path
        """
        ret = {k: v for k, v in old.items()}

        for key, val in new.items():
            if isinstance(val, collections.Mapping):
                ret[key] = self.update_dict(ret.get(key, {}), val)
            else:
                ret[key] = new[key]
        return ret

    def build_update_dict(self, path, val):
        """
        Build a new nested dictionary following a series of keys
        with a an endpoint value
        """
        ret = {}

        if len(path) > 1:
            ret[path[0]] = self.build_update_dict(path[1:], val)
        elif len(path) == 1:
            ret[path[0]] = val

        return ret

    def delete_key_loc(self, old, path):
        """
        Delete a key from a nested dictionary
        """
        ret = {k: v for k, v in old.items()}

        if len(path) > 1:
            ret[path[0]] = self.delete_key_loc(ret.get(path[1], {}), path[1:])
        elif len(path) == 1:
            ret.pop(path[0], None)

        return ret
