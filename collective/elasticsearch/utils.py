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
