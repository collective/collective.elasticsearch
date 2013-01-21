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
    # XXX NEED TO DO THIS A BETTER WAY!?
    obj = aq_base(obj)
    try:
        return str(u64(obj._p_oid))
    except:
        return getUID(obj)
