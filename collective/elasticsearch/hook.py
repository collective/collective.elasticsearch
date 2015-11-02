import logging
import traceback

from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch.utils import getUID
from plone import api
from plone.indexer.interfaces import IIndexableObject
from plone.indexer.interfaces import IIndexer
import transaction
from zope.component import queryMultiAdapter
from zope.globalrequest import getRequest

logger = logging.getLogger('collective.elasticsearch')

_req_cache_key = 'collective.elasticsearch.cachedHook'


class CommitHook(object):

    def __init__(self, es):
        self.remove = []
        self.index = {}
        self.cached_index_data = {}
        self.es = es

    def __call__(self, trns):
        es = self.es
        conn = es.connection

        if len(self.remove) > 0:
            bulk_data = []
            for uid in self.remove:
                bulk_data.append({
                    'delete': {
                        '_index': es.index_name,
                        '_type': es.doc_type,
                        '_id': uid
                    }
                })
            es.connection.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)

        if len(self.index) > 0:
            bulk_data = []
            bulk_size = es.get_setting('bulk_size', 50)

            for uid, obj in self.index.items():
                bulk_data.extend([{
                    'index': {
                        '_index': es.index_name,
                        '_type': es.doc_type,
                        '_id': uid
                    }
                }, self.get_index_data(uid, obj)])
                if len(bulk_data) % bulk_size == 0:
                    conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)
                    bulk_data = []

            if len(bulk_data) > 0:
                conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)

        self.index = {}
        self.remove = []
        self.cached_index_data = {}
        req = getRequest()
        if req and _req_cache_key in req.environ:
            del req.environ[_req_cache_key]

    def get_wrapped_object(self, obj):
        wrapped_object = None
        if not IIndexableObject.providedBy(obj):
            # This is the CMF 2.2 compatible approach, which should be used
            # going forward
            wrapper = queryMultiAdapter((obj, self.es.catalogtool),
                                        IIndexableObject)
            if wrapper is not None:
                wrapped_object = wrapper
            else:
                wrapped_object = obj
        else:
            wrapped_object = obj
        return wrapped_object

    def get_index_data(self, uid, obj):
        catalog = self.es.catalogtool._catalog

        index_data = {}
        for index_name in catalog.indexes.keys():
            index = getIndex(catalog, index_name)
            if index is not None:
                try:
                    value = index.get_value(self.get_wrapped_object(obj))
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


def getHook(es=None):
    # cache this call on the request obj
    req = getRequest()
    if req and _req_cache_key in req.environ:
        return req.environ[_req_cache_key]

    if es is None:
        from collective.elasticsearch.es import ElasticSearchCatalog
        es = ElasticSearchCatalog(api.portal.get_tool('portal_catalog'))
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