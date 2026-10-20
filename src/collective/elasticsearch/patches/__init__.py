from collective.elasticsearch.manager import ElasticSearchManager
from collective.elasticsearch.utils import get_brain_from_path
from Products.CMFCore.interfaces import IContentish

import transaction


def unrestrictedSearchResults(self, REQUEST=None, **kw):
    manager = ElasticSearchManager()
    active = manager.active
    method = manager.search_results if active else self._old_unrestrictedSearchResults
    return method(REQUEST, check_perms=False, **kw)


def safeSearchResults(self, REQUEST=None, **kw):
    manager = ElasticSearchManager()
    active = manager.active
    method = manager.search_results if active else self._old_searchResults
    return method(REQUEST, check_perms=True, **kw)


def delete_from_elasticsearch(status, data):
    if status:
        ElasticSearchManager().bulk(data=data)


def manage_uncatalogObject(self, REQUEST, RESPONSE, URL1, urls=None):
    """Remove the entries from the catalog and from elasticsearch."""
    manager = ElasticSearchManager()
    if manager.active and urls:
        urls = (urls,) if isinstance(urls, str) else urls
        brains = [get_brain_from_path(self._catalog, path) for path in urls]
        data = [("delete", brain.UID, {}) for brain in brains if brain]
        if data:
            transaction.get().addAfterCommitHook(delete_from_elasticsearch, (data,))
    return self._old_manage_uncatalogObject(REQUEST, RESPONSE, URL1, urls=urls)


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
