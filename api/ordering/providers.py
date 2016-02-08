""" Module to glue interfaces to implementations """

from api.providers.inventory import MockInventoryProvider
from api.providers.metrics import MockMetricsProvider
from api.providers.ordering import MockOrderingProvider
from api.providers.validation import MockValidationProvider
from api.providers.ordering.ordering_provider import OrderingProvider
from api.providers.validation import ValidationProvider


class DefaultProviders(object):
    api_versions = {"versions":
                        {"0":
                            {"description": "demo access points for development"}
                        }
                    }

    ordering = OrderingProvider()

    validation = ValidationProvider()

    metrics = MockMetricsProvider()

    inventory = MockInventoryProvider()


class MockProviders(object):
    ordering = MockOrderingProvider()

    validation = MockValidationProvider()

    metrics = MockMetricsProvider()

    inventory = MockInventoryProvider()
