from collective.elasticsearch.manager import ElasticSearchManager
from collective.elasticsearch.utils import get_brain_from_path
from Products.CMFCore.interfaces import IContentish


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
