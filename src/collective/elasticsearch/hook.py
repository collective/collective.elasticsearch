# -*- coding: utf-8 -*-
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
from zope.component import getAdapters
from zope.component import queryMultiAdapter
from zope.component.hooks import getSite
from zope.component.hooks import setSite

import logging
import random
import six
import time
import traceback
import transaction
import urllib3


logger = logging.getLogger('collective.elasticsearch')


def index_batch(remove, index, positions, es=None):  # noqa: C901
    if es is None:
        from collective.elasticsearch.es import ElasticSearchCatalog
        es = ElasticSearchCatalog(api.portal.get_tool('portal_catalog'))

    setSite(api.portal.get())
    conn = es.connection
    bulk_size = es.get_setting('bulk_size', 50)

    if len(remove) > 0:
        bulk_data = []
        for uid in remove:
            bulk_data.append({
                'delete': {
                    '_index': es.index_name,
                    '_id': uid
                }
            })
        result = es.connection.bulk(
            index=es.index_name,
            body=bulk_data)

        if "errors" in result and result["errors"] is True:
            logger.error("Error in bulk indexing removal: %s" % result)

    if len(index) > 0:
        if type(index) in (list, tuple, set):
            # does not contain objects, must be async, convert to dict
            index = dict([(k, None) for k in index])
        bulk_data = []

        for uid, obj in index.items():
            # If content has been moved (ie by a contentrule) then the object
            # passed here is the original object, not the moved one.
            # So if there is a uuid, we use this to get the correct object.
            # See https://github.com/collective/collective.elasticsearch/issues/65 # noqa
            if uid is not None:
                obj = uuidToObject(uid)

            if obj is None:
                obj = uuidToObject(uid)
                if obj is None:
                    continue
            bulk_data.extend([{
                'index': {
                    '_index': es.index_name,
                    '_id': uid
                }
            }, get_index_data(obj, es)])
            if len(bulk_data) % bulk_size == 0:
                result = conn.bulk(
                    index=es.index_name,
                    body=bulk_data)

                if "errors" in result and result["errors"] is True:
                    logger.error("Error in bulk indexing: %s" % result)

                bulk_data = []

        if len(bulk_data) > 0:
            result = conn.bulk(
                index=es.index_name,
                body=bulk_data)

            if "errors" in result and result["errors"] is True:
                logger.error("Error in bulk indexing: %s" % result)

    if len(positions) > 0:
        bulk_data = []
        index = getIndex(es.catalogtool._catalog, 'getObjPositionInParent')
        for uid, ids in positions.items():
            if uid == '/':
                parent = getSite()
            else:
                parent = uuidToObject(uid)
            if parent is None:
                logger.warn('could not find object to index positions')
                continue
            for _id in ids:
                ob = parent[_id]
                wrapped_object = get_wrapped_object(ob, es)
                try:
                    value = index.get_value(wrapped_object)
                except Exception:
                    continue
                bulk_data.extend([{
                    'update': {
                        '_index': es.index_name,
                        '_id': IUUID(ob)
                    }
                }, {
                    'doc': {
                        'getObjPositionInParent': value
                    }
                }])
                if len(bulk_data) % bulk_size == 0:
                    conn.bulk(
                        index=es.index_name,
                        body=bulk_data)
                    bulk_data = []

        if len(bulk_data) > 0:
            conn.bulk(
                index=es.index_name,
                body=bulk_data)


def get_wrapped_object(obj, es):
    wrapped_object = None
    if not IIndexableObject.providedBy(obj):
        # This is the CMF 2.2 compatible approach, which should be used
        # going forward
        wrapper = queryMultiAdapter((obj, es.catalogtool),
                                    IIndexableObject)
        if wrapper is not None:
            wrapped_object = wrapper
        else:
            wrapped_object = obj
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
            except Exception:
                logger.error('Error indexing value: %s: %s\n%s' % (
                    '/'.join(obj.getPhysicalPath()),
                    index_name,
                    traceback.format_exc()))
                value = None
            if value in (None, 'None'):
                # yes, we'll index null data...
                value = None

            # Ignore errors in converting to unicode, so json.dumps
            # does not barf when we're trying to send data to ES.
            if six.PY2:
                if isinstance(value, str):
                    value = six.text_type(value, 'utf-8', 'ignore')
            else:
                if isinstance(value, bytes):
                    value = value.decode('utf-8', 'ignore')

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
                if six.PY2:
                    if isinstance(value, str):
                        value = six.text_type(value, 'utf-8', 'ignore')
                else:
                    if isinstance(value, bytes):
                        value = value.decode('utf-8', 'ignore')
                index_data[name] = val
            except Exception:
                logger.error('Error indexing value: %s: %s\n%s' % (
                    '/'.join(obj.getPhysicalPath()),
                    name,
                    traceback.format_exc()))
        else:
            val = getattr(obj, name, None)
            if callable(val):
                val = val()
            index_data[name] = val

    for _, adapter in getAdapters((obj,), IAdditionalIndexDataProvider):
        index_data.update(adapter(es, index_data))

    return index_data


try:
    from collective.celery import task

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


class CommitHook(object):

    def __init__(self, es):
        self.remove = set()
        self.index = {}
        self.positions = {}
        self.es = es

    def schedule_celery(self):
        index_batch_async.apply_async(
            args=[self.remove, self.index.keys(), self.positions],
            kwargs={},
            without_transaction=True)

    def __call__(self, trns):
        if not trns:
            return

        if CELERY_INSTALLED:
            self.schedule_celery()
        else:
            index_batch(self.remove, self.index, self.positions, self.es)

        self.index = {}
        self.remove = []
        self.positions = {}


def getHook(es=None):
    if es is None:
        from collective.elasticsearch.es import ElasticSearchCatalog
        es = ElasticSearchCatalog(api.portal.get_tool('portal_catalog'))
    if not es.enabled:
        return

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
        hook.positions['/'] = ids
    else:
        uid = getUID(obj)
        if uid is None:
            logger.error("Tried to index an object of None uid")
            return
        hook.positions[getUID(obj)] = ids
