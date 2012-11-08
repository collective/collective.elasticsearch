# 
# elasticsearch integration with plone
# this will essentially replace the portal_catalog
# 

from logging import getLogger
from collective.elasticsearch.utils import sid

from Products.ZCatalog.Lazy import LazyMap
from collective.elasticsearch.interfaces import IElasticSearchCatalog
from zope.interface import classImplements
from collective.elasticsearch.brain import BrainFactory
from collective.elasticsearch.query import QueryAssembler
from collective.elasticsearch.es import ElasticSearch


logger = getLogger(__name__)
info = logger.info


def catalog_object(self, object, uid=None, idxs=[],
                   update_metadata=1, pghandler=None):
    es = ElasticSearch(self)
    return es.catalog(object, uid, idxs, update_metadata, pghandler)


def uncatalog_object(self, object, *args, **kwargs):
    es = ElasticSearch(self)
    return es.uncatalog(object, *args, **kwargs)


def searchResults(self, REQUEST=None, **kw):
    es = ElasticSearch(self)
    return es.searchResults(REQUEST, check_perms=True, **kw)


def simpleQuery(self, **query):
    es = ElasticSearch(self)
    conn = es.conn
    qassembler = QueryAssembler(self)
    equery = qassembler(query)
    result = conn.search(equery, sid(self), self.getId())
    catalog = self._catalog
    factory = BrainFactory(catalog)
    count = result.count()
    result = LazyMap(factory, result, count)
    return result


topatch = {
    'catalog_object': catalog_object,
    'uncatalog_object': uncatalog_object,
    'searchResults': searchResults,
    '__call__': searchResults
}

from Products.CMFPlone.CatalogTool import CatalogTool
classestopatch = [
    CatalogTool,
]

patched = {}

def patch():
    prefix = '__old_'
    for klass in classestopatch:
        if not IElasticSearchCatalog.implementedBy(klass):
            patched[klass] = {}
            for name, method in topatch.items():
                classImplements(klass, IElasticSearchCatalog)
                old = getattr(klass, name, method)
                patched[klass][name] = old
                setattr(klass, prefix + name, old)
                setattr(klass, name, method)
                info('patched %s', str(getattr(klass, name)))


def initialize(context):
    patch()