from collective.elasticsearch import hook
from collective.elasticsearch.es import ElasticSearchCatalog
from plone import api


def catalog_object(self, obj, uid=None, idxs=None, update_metadata=1, pghandler=None):
    if idxs is None:
        idxs = []
    es = ElasticSearchCatalog(self)
    return es.catalog_object(obj, uid, idxs, update_metadata, pghandler)


def uncatalog_object(self, uid, obj=None, *args, **kwargs):  # NOQA W1113
    es = ElasticSearchCatalog(self)
    return es.uncatalog_object(uid, obj, *args, **kwargs)


def unrestrictedSearchResults(self, REQUEST=None, **kw):
    es = ElasticSearchCatalog(self)
    return es.searchResults(REQUEST, check_perms=False, **kw)


def safeSearchResults(self, REQUEST=None, **kw):
    es = ElasticSearchCatalog(self)
    return es.searchResults(REQUEST, check_perms=True, **kw)


def manage_catalogRebuild(self, *args, **kwargs):  # NOQA W0613
    """need to be publishable"""
    es = ElasticSearchCatalog(self)
    return es.manage_catalogRebuild(**kwargs)


def manage_catalogClear(self, *args, **kwargs):
    """need to be publishable"""
    es = ElasticSearchCatalog(self)
    return es.manage_catalogClear(*args, **kwargs)


def _unindexObject(self, ob):
    # same reason as the patch above, we need the actual object passed along
    # this handle dexterity types
    path = "/".join(ob.getPhysicalPath())
    return self.uncatalog_object(path, obj=ob)


def moveObjectsByDelta(self, ids, delta, subset_ids=None, suppress_events=False):
    res = self._old_moveObjectsByDelta(
        ids, delta, subset_ids=subset_ids, suppress_events=suppress_events
    )
    es = ElasticSearchCatalog(api.portal.get_tool("portal_catalog"))
    if es.enabled:
        if subset_ids is None:
            subset_ids = self.idsInOrder()
        hook.index_positions(self.context, subset_ids)
    return res


def PloneSite_moveObjectsByDelta(
    self, ids, delta, subset_ids=None, suppress_events=False
):
    res = self._old_moveObjectsByDelta(
        ids, delta, subset_ids=subset_ids, suppress_events=suppress_events
    )
    es = ElasticSearchCatalog(api.portal.get_tool("portal_catalog"))
    if es.enabled:
        if subset_ids is None:
            objects = list(self._objects)
            subset_ids = self.getIdsSubset(objects)
        hook.index_positions(self, subset_ids)
    return res
