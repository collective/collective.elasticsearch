from Acquisition import aq_base
from collective.elasticsearch.es import ElasticSearchCatalog
from collective.elasticsearch.interfaces import IElasticSearchCatalog
from logging import getLogger
from plone.folder.default import DefaultOrdering
from Products.Archetypes.CatalogMultiplex import CatalogMultiplex
from Products.Archetypes.utils import isFactoryContained
from Products.CMFCore.CatalogTool import CatalogTool as CMFCatalogTool
from Products.CMFPlone.CatalogTool import CatalogTool
from Products.CMFPlone.Portal import PloneSite
from zope.interface import classImplements

import inspect

original_PloneSite_moveObjectsByDelta = PloneSite.moveObjectsByDelta
original_unindexObjectCMF = CMFCatalogTool.unindexObject
original_unindexObject = CatalogMultiplex.unindexObject
original_moveObjectsByDelta = DefaultOrdering.moveObjectsByDelta


logger = getLogger(__name__)
info = logger.info


def catalog_object(self, object, uid=None, idxs=[],
                   update_metadata=1, pghandler=None):
    es = ElasticSearchCatalog(self)
    return es.catalog_object(object, uid, idxs, update_metadata, pghandler)


def uncatalog_object(self, uid, obj=None, *args, **kwargs):
    es = ElasticSearchCatalog(self)
    return es.uncatalog_object(uid, obj, *args, **kwargs)


def searchResults(self, REQUEST=None, **kw):
    es = ElasticSearchCatalog(self)
    return es.searchResults(REQUEST, check_perms=False, **kw)


def safeSearchResults(self, REQUEST=None, **kw):
    es = ElasticSearchCatalog(self)
    return es.searchResults(REQUEST, check_perms=True, **kw)


def manage_catalogRebuild(self, *args, **kwargs):
    """ need to be publishable """
    es = ElasticSearchCatalog(self)
    return es.manage_catalogRebuild(**kwargs)


def manage_catalogClear(self, *args, **kwargs):
    """ need to be publishable """
    es = ElasticSearchCatalog(self)
    return es.manage_catalogClear(*args, **kwargs)


default_patch_map = {
    'catalog_object': catalog_object,
    'uncatalog_object': uncatalog_object,
    'searchResults': safeSearchResults,
    '__call__': safeSearchResults,
    'unrestrictedSearchResults': searchResults,
    'manage_catalogRebuild': manage_catalogRebuild,
    'manage_catalogClear': manage_catalogClear,
    'refreshCatalog': refreshCatalog
}


class Patch(object):
    def __init__(self, kls, method_map=default_patch_map):
        self.kls = kls
        self.method_map = method_map


patches = [
    Patch(CatalogTool)
]
patched = {}


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


def unindexObjectCMF(self, ob):
    # same reason as the patch above, we need the actual object passed along
    # this handle dexterity types
    path = '/'.join(ob.getPhysicalPath())
    return self.uncatalog_object(path, obj=ob)


def indexPositions(context, ids):
    for id in ids:
        if id.startswith('portal_'):
            continue
        ob = context[id]
        if not hasattr(ob, 'reindexObject'):
            continue
        if len(inspect.getargspec(ob.reindexObject).args) == 2:
            # XXX ONLY reindex EL
            ob.reindexObject(idxs=['getObjPositionInParent'])


def moveObjectsByDelta(self, ids, delta, subset_ids=None,
                       suppress_events=False):
    res = original_moveObjectsByDelta(self, ids, delta, subset_ids=subset_ids,
                                      suppress_events=suppress_events)
    if subset_ids is None:
        subset_ids = self.idsInOrder()
    indexPositions(self.context, subset_ids)
    return res


def PloneSite_moveObjectsByDelta(self, ids, delta, subset_ids=None,
                                 suppress_events=False):
    res = original_PloneSite_moveObjectsByDelta(
        self, ids, delta, subset_ids=subset_ids,
        suppress_events=suppress_events)
    if subset_ids is None:
        objects = list(self._objects)
        subset_ids = self.getIdsSubset(objects)
    indexPositions(self, subset_ids)
    return res


def patch():
    CMFCatalogTool.unindexObject = unindexObjectCMF
    setattr(CMFCatalogTool, '__old_unindexObject', original_unindexObjectCMF)

    CatalogMultiplex.unindexObject = unindexObject
    setattr(CatalogMultiplex, '__old_unindexObject', original_unindexObject)

    DefaultOrdering.moveObjectsByDelta = moveObjectsByDelta
    setattr(DefaultOrdering, '__old_moveObjectsByDelta',
            original_moveObjectsByDelta)

    PloneSite.moveObjectsByDelta = PloneSite_moveObjectsByDelta
    setattr(PloneSite, '__old_moveObjectsByDelta',
            original_PloneSite_moveObjectsByDelta)

    prefix = '__old_'
    for patch in patches:
        klass = patch.kls
        if not IElasticSearchCatalog.implementedBy(klass):
            patched[klass] = {}
            for name, method in patch.method_map.items():
                if not hasattr(klass, prefix + name):
                    classImplements(klass, IElasticSearchCatalog)
                    old = getattr(klass, name, method)
                    patched[klass][name] = old
                    setattr(klass, prefix + name, old)
                    setattr(klass, name, method)
                    info('patched %s', str(getattr(klass, name)))


def initialize(context):
    patch()
