from Acquisition import Implicit, aq_get
from Products.ZCatalog.interfaces import ICatalogBrain
from zope.interface import implements
from zope.globalrequest import getRequest
from Products.CMFPlone.utils import pretty_title_or_id
from collective.elasticsearch.ejson import loads

_marker = []


class Brain(Implicit):
    """
    A special brain implementation that uses the results
    from elasticsearch to load the brain.
    """
    implements(ICatalogBrain)
    __allow_access_to_unprotected_subobjects__ = True

    def __init__(self, data, catalog):
        self._idata = data
        self._raw_data = self._idata['_metadata']
        self._data = None
        self._catalog = catalog

    @property
    def data(self):
        if self._data is None:
            self._data = loads(self._raw_data)
        return self._data

    def has_key(self, key):
        return key in self.data
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
        if name in self.data:
            return self.data[name]
        elif name.startswith('portal_'):
            # XXX really ugly...
            return aq_get(self._catalog, name)

    def getPath(self):
        return '/'.join(self.getRawPath())

    def getRawPath(self):
        try:
            # need to convert to string because we get
            # unicode from elastic
            path = self.data['_path']
            newpath = []
            for part in path:
                newpath.append(str(part))
            return tuple(newpath)
        except KeyError:
            return ()

    def getURL(self, relative=0):
        request = aq_get(self._catalog, 'REQUEST', None)
        if request is None:
            request = getRequest()
        return request.physicalPathToURL(self.getPath(), relative)

    def _unrestrictedGetObject(self):
        return self._catalog.unrestrictedTraverse(self.getPath())

    def getObject(self, REQUEST=None):
        path = self.getRawPath()
        if not path:
            return None
        if len(path) > 1:
            parent = self._catalog.unrestrictedTraverse(path[:-1])
        else:
            return ''

        return parent.restrictedTraverse(path[-1])

    def getRID(self):
        """Return the record ID for this object."""
        return self.data.get_id()


def BrainFactory(catalog):
    def factory(result):
        brain = Brain(result, catalog)
        return brain.__of__(catalog)
    return factory
