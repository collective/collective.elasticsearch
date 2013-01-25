from logging import getLogger

from Acquisition import aq_base
from zope.interface import classImplements
from Products.Archetypes.utils import isFactoryContained

from collective.elasticsearch.interfaces import IElasticSearchCatalog
from collective.elasticsearch.es import ElasticSearch


logger = getLogger(__name__)
info = logger.info


def catalog_object(self, object, uid=None, idxs=[],
                   update_metadata=1, pghandler=None):
    es = ElasticSearch(self)
    return es.catalog_object(object, uid, idxs, update_metadata, pghandler)


def uncatalog_object(self, uid, obj=None, *args, **kwargs):
    es = ElasticSearch(self)
    return es.uncatalog_object(uid, obj, *args, **kwargs)


def searchResults(self, REQUEST=None, **kw):
    es = ElasticSearch(self)
    return es.searchResults(REQUEST, check_perms=False, **kw)


def safeSearchResults(self, REQUEST=None, **kw):
    es = ElasticSearch(self)
    return es.searchResults(REQUEST, check_perms=True, **kw)


def manage_catalogRebuild(self, REQUEST=None, RESPONSE=None):
    """ need to be publishable """
    es = ElasticSearch(self)
    return es.manage_catalogRebuild(REQUEST, RESPONSE)


def manage_catalogClear(self, REQUEST=None, RESPONSE=None, URL1=None):
    """ need to be publishable """
    es = ElasticSearch(self)
    return es.manage_catalogClear(REQUEST, RESPONSE, URL1)


def refreshCatalog(self, clear=0, pghandler=None):
    """ need to be publishable """
    es = ElasticSearch(self)
    return es.refreshCatalog(clear, pghandler)


default_patch_map = {
    'catalog_object': catalog_object,
    'uncatalog_object': uncatalog_object,
    'searchResults': safeSearchResults,
    '__call__': safeSearchResults,
    'manage_catalogRebuild': manage_catalogRebuild,
    'manage_catalogClear': manage_catalogClear,
    'refreshCatalog': refreshCatalog
}
unsafe_patch_map = default_patch_map.copy()
del unsafe_patch_map['__call__']
unsafe_patch_map['searchResults'] = searchResults


class Patch(object):
    def __init__(self, kls, method_map=default_patch_map):
        self.kls = kls
        self.method_map = method_map


from Products.CMFPlone.CatalogTool import CatalogTool
patches = [
    Patch(CatalogTool)
]
patched = {}


from Products.Archetypes.CatalogMultiplex import CatalogMultiplex
original_unindexObject = CatalogMultiplex.unindexObject

# archetypes unindexObject
def unindexObject(self):
    if isFactoryContained(self):
        return
    catalogs = self.getCatalogs()
    url = '/'.join(self.getPhysicalPath())
    for catalog in catalogs:
        # because we need the actual object for us to uncatalog...
        if type(aq_base(catalog)) in patched:
            catalog.uncatalog_object(url, self)
        elif catalog._catalog.uids.get(url, None) is not None:
            catalog.uncatalog_object(url)


def patch():
    prefix = '__old_'
    for patch in patches:
        klass = patch.kls
        if not IElasticSearchCatalog.implementedBy(klass):
            patched[klass] = {}
            for name, method in patch.method_map.items():
                classImplements(klass, IElasticSearchCatalog)
                old = getattr(klass, name, method)
                patched[klass][name] = old
                setattr(klass, prefix + name, old)
                setattr(klass, name, method)
                info('patched %s', str(getattr(klass, name)))

    
    CatalogMultiplex.unindexObject = unindexObject
    setattr(CatalogMultiplex, '__old_unindexObject', original_unindexObject)


def initialize(context):
    patch()
