from Products.ZCatalog.interfaces import ICatalogBrain
from Acquisition import Implicit, aq_get, aq_parent, aq_base
from pkg_resources import DistributionNotFound
from pkg_resources import get_distribution
from ZPublisher.BaseRequest import RequestContainer
from zope.interface import implements
from collective.elasticsearch.indexes import getIndex

try:
    get_distribution('five.globalrequest')
except DistributionNotFound:
    _GLOBALREQUEST_INSTALLED = False
else:
    _GLOBALREQUEST_INSTALLED = True

if _GLOBALREQUEST_INSTALLED:
    from zope.globalrequest import getRequest

_marker = []


class Brain(Implicit):
    implements(ICatalogBrain)

    def __init__(self, data, catalog):
        self._data = data
        self._catalog = catalog

    def has_key(self, key):
        return key in self._data
    __contains__ = has_key

    def __getattr__(self, name, default=_marker):
        if name == 'REQUEST':
            request = aq_get(self._catalog, 'REQUEST', None)
            if request is None and _GLOBALREQUEST_INSTALLED:
                request = getRequest()
            return request
        elif name[0] == '_':
            try:
                return self.__dict__[name]
            except KeyError:
                if default == _marker:
                    raise AttributeError(name)
                else:
                    return default
        index = getIndex(self._catalog, name)
        if index is not None:
            return index.extract(name, self._data)
        elif name in self._data:
            return self._data[name]
        elif name.startswith('portal_'):
            # XXX really ugly...
            return aq_get(self._catalog, name)

    def getPath(self):
        return str(self.path)

    def getURL(self, relative=0):
        request = aq_get(self._catalog, 'REQUEST', None)
        if request is None and _GLOBALREQUEST_INSTALLED:
            request = getRequest()
        return request.physicalPathToURL(self.getPath(), relative)

    def _unrestrictedGetObject(self):
        return self._catalog.unrestrictedTraverse(self.getPath())

    def getObject(self, REQUEST=None):
        path = self.getPath().split('/')
        if not path:
            return None
        if len(path) > 1:
            parent = self._catalog.unrestrictedTraverse(path[:-1])

        return parent.restrictedTraverse(path[-1])

    def getRID(self):
        """Return the record ID for this object."""
        return self._data.get_id()


def BrainFactory(catalog):
    def factory(result):
        brain = Brain(result, catalog)
        return brain.__of__(catalog)
    return factory
