# 
# elasticsearch integration with plone
# this will essentially replace the portal_catalog
# 

from logging import getLogger

from collective.elasticsearch.interfaces import IElasticSearchCatalog
from zope.interface import classImplements
from collective.elasticsearch.es import ElasticSearch

logger = getLogger(__name__)
info = logger.info


def catalog_object(self, object, uid=None, idxs=[],
                   update_metadata=1, pghandler=None):
    es = ElasticSearch(self)
    return es.catalog_object(object, uid, idxs, update_metadata, pghandler)


def uncatalog_object(self, object, *args, **kwargs):
    es = ElasticSearch(self)
    return es.uncatalog_object(object, *args, **kwargs)


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


def initialize(context):
    patch()