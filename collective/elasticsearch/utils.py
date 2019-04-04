# -*- coding: utf-8 -*-
from collective.elasticsearch.interfaces import IElasticSettings
from plone.registry.interfaces import IRegistry
from zope.component import getUtility


try:
    from plone.uuid.interfaces import IUUID
except ImportError:
    def IUUID(obj, default=None):
        return default


def getUID(obj):
    value = IUUID(obj, None)
    if not value and hasattr(obj, 'UID'):
        value = obj.UID()
    return value


def getESOnlyIndexes():
    default = {'Title': 2, 'Description': 0, 'SearchableText': 0}
    try:
        indexes = getUtility(IRegistry).forInterface(
            IElasticSettings,
            check=False
        ).es_only_indexes
        values = {}
        for i in indexes:
            name = i.split(':')[0]
            values[name] = 0
            if len(i.split(':')) == 2:
                try:
                    values[name] = float(i.split(':')[1])
                except ValueError:
                    pass
        return values

    except (KeyError, AttributeError):
        return default
