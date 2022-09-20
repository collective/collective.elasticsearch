from collective.elasticsearch import interfaces
from collective.elasticsearch.manager import ElasticSearchManager
from plone.folder.interfaces import IOrdering
from Products.CMFCore.indexing import processQueue
from Products.CMFCore.interfaces import IContentish
from zope.globalrequest import getRequest
from zope.interface import alsoProvides
from zope.interface import noLongerProvides


def unrestrictedSearchResults(self, REQUEST=None, **kw):
    manager = ElasticSearchManager()
    return manager.search_results(REQUEST, check_perms=False, **kw)


def safeSearchResults(self, REQUEST=None, **kw):
    manager = ElasticSearchManager()
    return manager.search_results(REQUEST, check_perms=True, **kw)


def manage_catalogRebuild(self, *args, **kwargs):  # NOQA W0613
    """need to be publishable"""
    manager = ElasticSearchManager()
    if manager.enabled:
        manager._recreate_catalog()

    alsoProvides(getRequest(), interfaces.IReindexActive)
    result = self._old_manage_catalogRebuild(*args, **kwargs)
    processQueue()
    manager.flush_indices()
    noLongerProvides(getRequest(), interfaces.IReindexActive)
    return result


def manage_catalogClear(self, *args, **kwargs):
    """need to be publishable"""
    manager = ElasticSearchManager()
    if not manager.active:
        manager._recreate_catalog()
    return self._old_manage_catalogClear(*args, **kwargs)


def get_ordered_ids(context) -> dict:
    """Return all object ids in a context, ordered."""
    if IOrdering.providedBy(context):
        return {oid: idx for idx, oid in enumerate(context.idsInOrder())}
    else:
        # For Plone 5.2, we care only about Dexterity content
        objects = [
            obj
            for obj in list(context._objects)
            if obj.get("meta_type").startswith("Dexterity")
        ]
        return {oid: idx for idx, oid in enumerate(context.getIdsSubset(objects))}


def moveObjectsByDelta(self, ids, delta, subset_ids=None, suppress_events=False):
    manager = ElasticSearchManager()
    ordered = self if IOrdering.providedBy(self) else None
    before = get_ordered_ids(self)
    res = self._old_moveObjectsByDelta(
        ids, delta, subset_ids=subset_ids, suppress_events=suppress_events
    )
    if manager.active:
        after = get_ordered_ids(self)
        diff = [oid for oid, idx in after.items() if idx != before[oid]]
        context = self.context if ordered else self
        for oid in diff:
            obj = context[oid]
            # We only reindex content objects
            if not IContentish.providedBy(obj):
                continue
            obj.reindexObject(idxs=["getObjPositionInParent"])
    return res
