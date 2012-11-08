from Acquisition import aq_base
from ZODB.utils import u64
try:
    from plone.uuid.interfaces import IUUID
except:
    def IUUID(obj, default=None):
        return default


def getUID(obj):
    value = IUUID(obj, None)
    if not value and hasattr(obj, 'UID'):
        value = obj.UID()
    return value


def sid(obj):
    obj = aq_base(obj)
    try:
        return str(u64(obj._p_oid))
    except:
        return getUID(obj)
