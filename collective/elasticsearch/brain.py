from Products.ZCatalog.interfaces import ICatalogBrain
from Acquisition import Implicit, aq_get
from zope.interface import implements
from collective.elasticsearch.indexes import getIndex
from zope.globalrequest import getRequest
from Products.CMFPlone.utils import pretty_title_or_id

_marker = []


class Brain(Implicit):
    implements(ICatalogBrain)
    __allow_access_to_unprotected_subobjects__ = True

    def __init__(self, data, catalog):
        self._data = data
        self._catalog = catalog

    def has_key(self, key):
        return key in self._data
    __contains__ = has_key

    @property
    def pretty_title_or_id(self):
        return pretty_title_or_id(self._catalog, self)

    def __getattr__(self, name, default=_marker):
        if name == 'REQUEST':
            request = aq_get(self._catalog, 'REQUEST', None)
            if request is None:
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
        if request is None:
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
        else:
            return ''

        return parent.restrictedTraverse(path[-1])

    def getRID(self):
        """Return the record ID for this object."""
        return self._data.get_id()


def BrainFactory(catalog):
    def factory(result):
        brain = Brain(result, catalog)
        return brain.__of__(catalog)
    return factory
