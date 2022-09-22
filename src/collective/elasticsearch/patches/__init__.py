from collective.elasticsearch import interfaces
from collective.elasticsearch.manager import ElasticSearchManager
from plone.folder.interfaces import IOrdering
from Products.CMFCore.indexing import processQueue
from Products.CMFCore.interfaces import IContentish
from time import process_time
from zope.globalrequest import getRequest
from zope.interface import alsoProvides
from zope.interface import noLongerProvides

import time
import urllib


def unrestrictedSearchResults(self, REQUEST=None, **kw):
    manager = ElasticSearchManager()
    active = manager.active
    method = manager.search_results if active else self._old_unrestrictedSearchResults
    return method(REQUEST, check_perms=False, **kw)


def safeSearchResults(self, REQUEST=None, **kw):
    manager = ElasticSearchManager()
    active = manager.active
    method = manager.search_results if active else self._old_unrestrictedSearchResults
    return method(REQUEST, check_perms=True, **kw)


def manage_catalogRebuild(self, RESPONSE=None, URL1=None):  # NOQA W0613
    """need to be publishable"""
    manager = ElasticSearchManager()
    if manager.enabled:
        manager._recreate_catalog()
        alsoProvides(getRequest(), interfaces.IReindexActive)

    elapse = time.time()
    c_elapse = process_time()

    self.clearFindAndRebuild()

    elapse = time.time() - elapse
    c_elapse = process_time() - c_elapse

    msg = f"Catalog Rebuilt\nTotal time: {elapse}\nTotal CPU time: {c_elapse}"

    if manager.enabled:
        processQueue()
        manager.flush_indices()
        noLongerProvides(getRequest(), interfaces.IReindexActive)
    if RESPONSE is not None:
        RESPONSE.redirect(
            URL1
            + "/manage_catalogAdvanced?manage_tabs_message="
            + urllib.parse.quote(msg)
        )


def manage_catalogClear(self, *args, **kwargs):
    """need to be publishable"""
    manager = ElasticSearchManager()
    if manager.enabled and not manager.active:
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
