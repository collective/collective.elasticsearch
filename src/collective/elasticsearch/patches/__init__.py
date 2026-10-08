from collective.elasticsearch import interfaces
from collective.elasticsearch import logger
from collective.elasticsearch.manager import ElasticSearchManager
from collective.elasticsearch.utils import get_brain_from_path
from collective.elasticsearch.utils import getESOnlyIndexes
from Products.CMFCore.indexing import processQueue
from Products.CMFCore.interfaces import IContentish
from time import process_time
from zope.globalrequest import getRequest
from zope.interface import alsoProvides
from zope.interface import noLongerProvides

import time
import urllib


def route_search(catalog, request, kw, check_perms):
    """Send catalog queries using elasticsearch only indexes to elasticsearch."""
    if check_perms:
        original = catalog._old_searchResults
    else:
        original = catalog._old_unrestrictedSearchResults
    query = request.copy() if isinstance(request, dict) else {}
    query.update(kw)
    manager = ElasticSearchManager()
    if not (manager.active and getESOnlyIndexes().intersection(query)):
        return original(request, **kw)

    logger.debug(f"Running query: {query}")
    try:
        if check_perms:
            return manager.secure_search(query)
        # Make sure any pending index tasks have been processed
        processQueue()
        return manager.search(query)
    except Exception:  # NOQA W0703
        if manager.raise_search_exception is True:
            raise
        logger.error(f"Error running Query: {query}", exc_info=True)
        return original(request, **kw)


def unrestrictedSearchResults(self, REQUEST=None, **kw):
    return route_search(self, REQUEST, kw, check_perms=False)


def safeSearchResults(self, REQUEST=None, **kw):
    return route_search(self, REQUEST, kw, check_perms=True)


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


def uncatalog_object(self, *args, **kwargs):
    manager = ElasticSearchManager()
    if manager.active:
        # If ES is active, we also remove the record from there
        zcatalog = self._catalog
        data = []
        for path in args:
            brain = get_brain_from_path(zcatalog, path)
            if not brain:
                # Path not in the catalog
                continue
            data.append(("delete", brain.UID, {}))
        manager.bulk(data=data)
    return self._old_uncatalog_object(*args, **kwargs)


def get_ordered_ids(ordering) -> dict:
    """Return all object ids of an ordering, mapped to their position."""
    return {oid: idx for idx, oid in enumerate(ordering.idsInOrder())}


def moveObjectsByDelta(self, ids, delta, subset_ids=None, suppress_events=False):
    manager = ElasticSearchManager()
    before = get_ordered_ids(self)
    res = self._old_moveObjectsByDelta(
        ids, delta, subset_ids=subset_ids, suppress_events=suppress_events
    )
    if manager.active:
        after = get_ordered_ids(self)
        diff = [oid for oid, idx in after.items() if idx != before[oid]]
        for oid in diff:
            obj = self.context[oid]
            # We only reindex content objects
            if not IContentish.providedBy(obj):
                continue
            obj.reindexObject(idxs=["getObjPositionInParent"])
    return res
