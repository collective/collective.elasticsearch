from plone.app.uuid.utils import uuidToObject
from plone import api
from collective.elasticsearch.es import ElasticSearchCatalog
from plone.indexer.interfaces import IIndexableObject
from collective.elasticsearch.utils import getUID
from plone.app.iterate.browser import info
from zope.component import queryMultiAdapter
from collective.elasticsearch.indexes import getIndex
import transaction
import traceback

try:
    from collective.celery import task

    @task()
    def remove_from_el_async(uids):
        _remove_from_el(uids)

    @task()
    def index_el_async(uids):
        data = {}
        for uid in uids:
            data[uid] = uuidToObject(uid)
        _index_in_el(data)

    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False


def _remove_from_el(uids):
    es = ElasticSearchCatalog(api.portal.get_tool('portal_catalog'))
    bulk_data = []
    for uid in uids:
        bulk_data.append({
            'delete': {
                '_index': es.index_name,
                '_type': es.doc_type,
                '_id': uid
            }
        })
    es.conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)


def _get_index_data(catalogtool, obj):
    catalog = catalogtool._catalog

    wrapped_object = None
    if not IIndexableObject.providedBy(obj):
        # This is the CMF 2.2 compatible approach, which should be used
        # going forward
        wrapper = queryMultiAdapter((obj, catalogtool),
                                    IIndexableObject)
        if wrapper is not None:
            wrapped_object = wrapper
        else:
            wrapped_object = obj
    else:
        wrapped_object = obj
    idxs = catalog.indexes.keys()
    index_data = {}
    for index_name in idxs:
        index = getIndex(catalog, index_name)
        if index is not None:
            try:
                value = index.get_value(wrapped_object)
            except:
                info('Error indexing value: %s: %s\n%s' % (
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
    return index_data


def _index_in_el(data):
    es = ElasticSearchCatalog(api.portal.get_tool('portal_catalog'))
    conn = es.connection

    bulk_data = []
    bulk_size = es.get_setting('bulk_size', 50)

    for uid, obj in data.items():
        bulk_data.extend([{
            'index': {
                '_index': es.index_name,
                '_type': es.doc_type,
                '_id': uid
            }
        }, _get_index_data(es.catalogtool, obj)])
        if len(bulk_data) % bulk_size == 0:
            conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)
            bulk_data = []

    if len(bulk_data) > 0:
        conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)


class CommitHook(object):

    def __init__(self, es):
        self.remove = []
        self.index = {}
        self.es = es

    def __call__(self):
        # use collective.celery if it is available
        if HAS_CELERY:
            remove_from_el_async.delay(self.remove)
            index_el_async.delay(self.index.keys())
        else:
            _remove_from_el(self.remove)
            _index_in_el(self.index)


def getHook(es):
    trns = transaction.get()
    hook = None
    for _hook in trns._after_commit:
        if isinstance(_hook, CommitHook):
            hook = _hook
            break
    if hook is None:
        hook = CommitHook(es)
        trns.addAfterCommitHook(hook)
        return hook


def remove_object(es, obj):
    hook = getHook()
    uid = getUID(obj)
    hook.remove.append(uid)


def add_object(es, obj):
    hook = getHook()
    hook.index[getUID(obj)] = obj