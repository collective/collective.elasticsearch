from collective.elasticsearch import logger
from collective.elasticsearch import utils
from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch.interfaces import IAdditionalIndexDataProvider
from collective.elasticsearch.utils import getESOnlyIndexes
from collective.elasticsearch.utils import getUID
from plone import api
from plone.app.uuid.utils import uuidToObject
from plone.indexer.interfaces import IIndexableObject
from plone.indexer.interfaces import IIndexer
from plone.uuid.interfaces import IUUID
from Products.CMFCore.interfaces import ISiteRoot
from typing import List
from zope.component import getAdapters
from zope.component import queryMultiAdapter
from zope.component.hooks import getSite
from zope.component.hooks import setSite

import random
import time
import traceback
import transaction
import urllib3


def get_es_catalog():
    from collective.elasticsearch.es import ElasticSearchCatalog

    return ElasticSearchCatalog(api.portal.get_tool("portal_catalog"))


def _bulk_call(conn, index_name, raw_data):
    """Bulk action on Elastic Search."""
    data = [item for sublist in raw_data for item in sublist]
    logger.debug(f"Bulk call with {len(raw_data)} entries and {len(data)} actions.")
    result = conn.bulk(index=index_name, body=data)
    if "errors" in result and result["errors"] is True:
        logger.error(f"Error in bulk operation: {result}")


def _remove_payload(index_name: str, es, to_remove: List) -> List[List[dict]]:
    """Payload for remove calls."""
    data = [{"delete": {"_index": index_name, "_id": uid}} for uid in to_remove]
    return data


def _index_payload(index_name: str, es, to_index: dict) -> List[List[dict]]:
    """Payload for indexing calls."""
    data = []
    for uid, obj in to_index.items():
        portal_type = obj.portal_type if obj else None
        if portal_type != "Plone Site":
            # If content has been moved (ie by a contentrule) then the object
            # passed here is the original object, not the moved one.
            # So if there is a uuid, we use this to get the correct object.
            # See https://github.com/collective/collective.elasticsearch/issues/65 # noqa
            if uid or obj is None:
                obj = uuidToObject(uid)

            if obj is None:
                continue
        data.append(
            [
                {"index": {"_index": index_name, "_id": uid}},
                get_index_data(obj, es),
            ]
        )
    return data


def _position_payload(index_name: str, es, to_up_position: dict) -> List[List[dict]]:
    """Payload for position calls."""
    data = []
    if not to_up_position:
        return data
    index = getIndex(es.catalogtool._catalog, "getObjPositionInParent")
    site = getSite()
    for uid, ids in to_up_position.items():
        parent = site if uid == "/" else uuidToObject(uid)
        if parent is None:
            logger.warning("could not find object to index positions")
            continue
        for _id in ids:
            ob = parent[_id]
            wrapped_object = get_wrapped_object(ob, es)
            try:
                value = index.get_value(wrapped_object)
            except Exception:  # NOQA W0703
                continue
            data.append(
                [
                    {"update": {"_index": index_name, "_id": IUUID(ob)}},
                    {"doc": {"getObjPositionInParent": value}},
                ],
            )
    return data


def index_batch(remove, index, positions, es=None):  # noqa: C901
    calls = 0
    setSite(api.portal.get())
    es = get_es_catalog() if es is None else es
    conn = es.connection
    index_name = es.index_name
    bulk_size = es.get_setting("bulk_size", 50)
    bulk_data = []

    to_remove = remove if remove else []
    to_up_positions = positions if positions else {}
    to_index = index if index else {}
    if type(to_index) in (list, tuple, set):
        # does not contain objects, must be async, convert to dict
        to_index = {k: None for k in to_index}

    process = [
        (_remove_payload, to_remove),
        (_position_payload, to_up_positions),
        (_index_payload, to_index),
    ]
    for func, data in process:
        raw_data = func(index_name, es, data)
        if raw_data:
            bulk_data.extend(raw_data)

    # Run calls
    for batch in utils.batches(bulk_data, bulk_size):
        _bulk_call(conn, index_name, batch)
        calls += 1

    conn.transport.close()
    return calls


def get_wrapped_object(obj, es):
    wrapped_object = None
    if not IIndexableObject.providedBy(obj):
        # This is the CMF 2.2 compatible approach, which should be used
        # going forward
        wrapper = queryMultiAdapter((obj, es.catalogtool), IIndexableObject)
        wrapped_object = wrapper if wrapper is not None else obj
    else:
        wrapped_object = obj
    return wrapped_object


def get_index_data(obj, es):  # noqa: C901
    catalog = es.catalogtool._catalog

    wrapped_object = get_wrapped_object(obj, es)
    index_data = {}
    for index_name in catalog.indexes.keys():
        index = getIndex(catalog, index_name)
        if index is not None:
            try:
                value = index.get_value(wrapped_object)
            except Exception:  # NOQA W0703
                path = "/".join(obj.getPhysicalPath())
                exception = traceback.format_exc()
                logger.error(f"Error indexing value: {path}: {index_name}\n{exception}")
                value = None
            if value in (None, "None"):
                # yes, we'll index null data...
                value = None

            # Ignore errors in converting to unicode, so json.dumps
            # does not barf when we're trying to send data to ES.
            value = (
                value.decode("utf-8", "ignore") if isinstance(value, bytes) else value
            )

            index_data[index_name] = value

    # in case these indexes are deleted
    # (to increase performance and improve ram usage)
    for name in getESOnlyIndexes():
        if name in index_data:
            continue
        indexer = queryMultiAdapter((obj, es.catalogtool), IIndexer, name=name)
        if indexer is not None:
            try:
                val = indexer()
                val = val.decode("utf-8", "ignore") if isinstance(val, bytes) else val
                index_data[name] = val
            except Exception:  # NOQA W0703
                path = "/".join(obj.getPhysicalPath())
                exception = traceback.format_exc()
                logger.error("Error indexing value: {path}: {name}\n{exception}")
        else:
            val = getattr(obj, name, None)
            if callable(val):
                val = val()
            index_data[name] = val

    for _, adapter in getAdapters((obj,), IAdditionalIndexDataProvider):
        index_data.update(adapter(es, index_data))

    return index_data


try:
    from collective.celery import task  # NOQA C0412

    @task.as_admin()
    def index_batch_async(remove, index, positions):
        retries = 0
        while True:
            # if doing batch updates, this can give ES problems
            if retries < 4:
                try:
                    index_batch(remove, index, positions)
                    break
                except urllib3.exceptions.ReadTimeoutError:
                    retries += 1
                    if retries >= 4:
                        raise
                    time.sleep(random.choice([0.5, 0.75, 1, 1.25, 1.5]))

    CELERY_INSTALLED = True
except ImportError:
    CELERY_INSTALLED = False


class CommitHook:
    def __init__(self, es):
        self.remove = set()
        self.index = {}
        self.positions = {}
        self.es = es

    def schedule_celery(self):
        index_batch_async.apply_async(
            args=[self.remove, self.index.keys(), self.positions],
            kwargs={},
            without_transaction=True,
        )

    def index_batch(self):
        to_remove = len(self.remove)
        to_index = len(self.index)
        to_positions = len(self.positions)
        logger.debug(
            f"Started batch calls: {to_remove} remove, {to_index} index, {to_positions} positions"  # noQA
        )
        total_calls = index_batch(self.remove, self.index, self.positions, self.es)
        logger.debug(f"Completed {total_calls}batch calls")

    def __call__(self, trns):
        if not trns:
            return

        if CELERY_INSTALLED:
            self.schedule_celery()
        else:
            self.index_batch()

        # Cleanup
        self.index = {}
        self.remove = []
        self.positions = {}


def getHook(es=None):
    es = get_es_catalog() if es is None else es
    if not es.enabled:
        return None
    trns = transaction.get()
    hook = None
    for _hook in trns._after_commit:
        if isinstance(_hook[0], CommitHook):
            hook = _hook[0]
            break
    if hook is None:
        hook = CommitHook(es)
        trns.addAfterCommitHook(hook)
    return hook


def remove_object(es, obj):
    hook = getHook(es)
    uid = getUID(obj)
    if uid is None:
        logger.error("Tried to unindex an object of None uid")
        return

    hook.remove.add(uid)
    if uid in hook.index:
        del hook.index[uid]


def add_object(es, obj):
    hook = getHook(es)
    uid = getUID(obj)
    if uid is None:
        logger.error("Tried to index an object of None uid")
        return

    hook.index[uid] = obj
    if uid in hook.remove:
        hook.remove.remove(uid)


def index_positions(obj, ids):
    hook = getHook()
    if ISiteRoot.providedBy(obj):
        hook.positions["/"] = ids
    else:
        uid = getUID(obj)
        if uid is None:
            logger.error("Tried to index an object of None uid")
            return
        hook.positions[getUID(obj)] = ids
