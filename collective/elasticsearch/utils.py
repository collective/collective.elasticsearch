from collective.elasticsearch.interfaces import IElasticSettings
from zope.component import getUtility
from plone.registry.interfaces import IRegistry

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
    return getUtility(IRegistry).forInterface(IElasticSettings).es_only_indexes
