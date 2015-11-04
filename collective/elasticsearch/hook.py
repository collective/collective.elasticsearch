import logging
import traceback

from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch.utils import getUID
from plone import api
from plone.app.uuid.utils import uuidToObject
from plone.indexer.interfaces import IIndexableObject
from plone.indexer.interfaces import IIndexer
import transaction
from zope.component import queryMultiAdapter


logger = logging.getLogger('collective.elasticsearch')


def index_batch(remove, index, es=None):
    if es is None:
        from collective.elasticsearch.es import ElasticSearchCatalog
        es = ElasticSearchCatalog(api.portal.get_tool('portal_catalog'))
    conn = es.connection

    if len(remove) > 0:
        bulk_data = []
        for uid in remove:
            bulk_data.append({
                'delete': {
                    '_index': es.index_name,
                    '_type': es.doc_type,
                    '_id': uid
                }
            })
        es.connection.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)

    if len(index) > 0:
        if type(index) in (list, tuple, set):
            # does not contain objects, must be async, convert to dict
            index = dict([(k, None) for k in index])
        bulk_data = []
        bulk_size = es.get_setting('bulk_size', 50)

        for uid, obj in index.items():
            if obj is None:
                obj = uuidToObject(uid)
                if obj is None:
                    continue
            bulk_data.extend([{
                'index': {
                    '_index': es.index_name,
                    '_type': es.doc_type,
                    '_id': uid
                }
            }, get_index_data(uid, obj, es)])
            if len(bulk_data) % bulk_size == 0:
                conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)
                bulk_data = []

        if len(bulk_data) > 0:
            conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)


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


def get_index_data(uid, obj, es):
    catalog = es.catalogtool._catalog

    index_data = {}
    for index_name in catalog.indexes.keys():
        index = getIndex(catalog, index_name)
        if index is not None:
            try:
                value = index.get_value(get_wrapped_object(obj, es))
            except:
                logger.info('Error indexing value: %s: %s\n%s' % (
                    '/'.join(obj.getPhysicalPath()),
                    index,
                    traceback.format_exc()))
                value = None
            if value in (None, 'None'):
                # yes, we'll index null data...
                value = None

            # Ignore errors in converting to unicode, so json.dumps
            # does not barf when we're trying to send data to ES.
            if isinstance(value, str):
                value = unicode(value, 'utf-8', 'ignore')

            index_data[index_name] = value

    # in case these indexes are deleted(to increase performance and improve ram usage)
    for name in ('SearchableText', 'Title', 'Description'):
        if name in index_data:
            continue
        indexer = queryMultiAdapter((obj, catalog), IIndexer, name=name)
        if indexer is not None:
            val = indexer()
            if isinstance(value, str):
                val = unicode(val, 'utf-8', 'ignore')
            index_data[name] = val

    return index_data


try:
    from collective.celery import task

    @task()
    def index_batch_async(remove, index):
        index_batch(remove, index)

    CELERY_INSTALLED = True
except ImportError:
    CELERY_INSTALLED = False


class CommitHook(object):

    def __init__(self, es):
        self.remove = []
        self.index = {}
        self.es = es

    def schedule_celery(self):
        index_batch_async.apply_async(
            args=[self.remove, self.index.keys()],
            kwargs={},
            without_transaction=True)

    def __call__(self, trns):
        if not trns:
            return

        if CELERY_INSTALLED:
            self.schedule_celery()
        else:
            index_batch(self.remove, self.index, self.es)

        self.index = {}
        self.remove = []


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
    hook.remove.append(uid)


def add_object(es, obj):
    hook = getHook(es)
    hook.index[getUID(obj)] = obj