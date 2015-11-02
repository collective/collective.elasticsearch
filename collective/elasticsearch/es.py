from logging import getLogger
import traceback

from Acquisition import aq_base
from DateTime import DateTime
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import _getAuthenticatedUser
from Products.ZCatalog.Lazy import LazyMap
from collective.elasticsearch import hook
from collective.elasticsearch.brain import BrainFactory
from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch.interfaces import IElasticSettings
from collective.elasticsearch.query import QueryAssembler
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError, ElasticsearchException
from plone.registry.interfaces import IRegistry
from zope.component import ComponentLookupError
from zope.component import getUtility


logger = getLogger(__name__)
info = logger.info
warn = logger.warn

CONVERTED_ATTR = '_elasticconverted'
CUSTOM_INDEX_NAME_ATTR = '_elasticcustomindex'


class PatchCaller(object):
    '''
    Very odd I have to do this. If I don't,
    I get very pecular errors trying to call
    the original methods
    '''

    def __init__(self, patched_object):
        self._patched_object = patched_object

    def __getattr__(self, name):
        '''
        assuming original attribute has '__old_' prefix
        '''
        if name[0] == '_':
            return self.__dict__[name]
        _type = type(aq_base(self._patched_object))
        func = getattr(_type, '__old_' + name)

        # 'bind' it
        def bound_func(*args, **kwargs):
            return func(self._patched_object, *args, **kwargs)
        return bound_func


class ElasticResult(object):

    def __init__(self, es, query):
        self.es = es
        self.bulk_size = es.get_setting('bulk_size', 50)
        qassembler = QueryAssembler(es.catalogtool)
        dquery, sort = qassembler.normalize(query)
        equery = qassembler(dquery)

        # results are stored in a dictionary, keyed
        # but the start index of the bulk size for the
        # results it holds. This way we can skip around
        # for result data in a result object
        self.query = self.make_query_transaction_aware(equery)
        result = es._search(self.query, sort=sort)['hits']
        self.results = {
            0: result['hits']
        }
        self.count = result['total']
        self.sort = sort

    def make_query_transaction_aware(self, query):
        '''
        IMPORTANT HERE!
        How we do transactiona awareness here is by disabling
        the querying of currently active transaction uids and then
        allowing the querying of transaction data.
        '''
        filters = [{'term': {'transaction': False}}]
        active = len(self.es.dm) > 0
        if active:
            filters.append({
                'and': [{'term': {'transaction_id': self.es.dm.transaction_id}},
                        {'term': {'transaction': True}}]
            })
        if filters > 1:
            filters = [{'or': filters}]
        if active:
            # filter out transaction items
            filters.append({
                'not': {
                    'term': {'_id': self.es.dm.keys()}
                }
            })
        query['filtered']['filter']['and'].extend(filters)
        return query

    def __getitem__(self, key):
        if isinstance(key, slice):
            return [self[i] for i in range(key.start, key.end)]
        else:
            if key >= self.count:
                raise IndexError
            result_key = (key / self.bulk_size) * self.bulk_size
            if result_key not in self.results:
                self.results[result_key] = self.es._search(
                    self.query, sort=self.sort, start=result_key)['hits']['hits']
            result_index = key % self.bulk_size
            return self.results[result_key][result_index]


class ElasticSearchCatalog(object):
    '''
    from patched methods
    '''

    def __init__(self, catalogtool):
        self.catalogtool = catalogtool
        self.catalog = catalogtool._catalog
        self.patched = PatchCaller(self.catalogtool)

        try:
            registry = getUtility(IRegistry)
            try:
                self.registry = registry.forInterface(IElasticSettings)
            except:
                self.registry = None
        except ComponentLookupError:
            self.registry = None

        self._conn = None

    @property
    def connection(self):
        if self._conn is None:
            self._conn = Elasticsearch(
                self.registry.hosts,
                timeout=self.get_setting('timeout', 0.5),
                sniff_on_start=self.get_setting('sniff_on_start', False),
                sniff_on_connection_fail=self.get_setting('sniff_on_connection_fail',
                                                          False),
                sniffer_timeout=self.get_setting('sniffer_timeout', 0.1),
                retry_on_timeout=self.get_setting('retry_on_timeout', False))
        return self._conn

    def _search(self, query, **query_params):
        '''
        '''
        if 'start' in query_params:
            query_params['from_'] = query_params.pop('start')
        query_params['fields'] = 'path.path'
        query_params['size'] = self.get_setting('bulk_size', 50)

        return self.connection.search(index=self.index_name,
                                      doc_type=self.doc_type,
                                      body={'query': query},
                                      **query_params)

    def search(self, query):
        result = ElasticResult(self, query)
        factory = BrainFactory(self.catalog)
        return LazyMap(factory, result, result.count)

    @property
    def catalog_converted(self):
        return getattr(self.catalogtool, CONVERTED_ATTR, False)

    @property
    def enabled(self):
        return self.registry.enabled

    def get_setting(self, name, default=None):
        return getattr(self.registry, name, default)

    def catalog_object(self, obj, uid=None, idxs=[], update_metadata=1, pghandler=None):
        self.patched.catalog_object(
            obj, uid, idxs, update_metadata, pghandler)
        if not self.enabled:
            return
        hook.add_object(obj)

    def uncatalog_object(self, uid, obj=None, *args, **kwargs):
        # always need to uncatalog to remove brains, etc
        result = self.patched.uncatalog_object(uid, *args, **kwargs)
        if self.enabled:
            hook.remove_object(obj)

        return result

    def manage_catalogRebuild(self, *args, **kwargs):
        if self.enabled:
            self.recreateCatalog()

        return self.patched.manage_catalogRebuild(*args, **kwargs)

    def manage_catalogClear(self, *args, **kwargs):
        if self.enabled:
            self.recreateCatalog()

        return self.patched.manage_catalogClear(*args, **kwargs)

    def recreateCatalog(self):
        conn = self.connection
        try:
            conn.indices.delete(index=self.index_name)
        except NotFoundError:
            pass
        self.convertToElastic()

    def searchResults(self, REQUEST=None, check_perms=False, **kw):
        enabled = False
        if self.enabled:
            # need to also check is it is a search result we care about
            # using EL for
            if 'Title' in kw or 'SearchableText' in kw or 'Description' in kw:
                # XXX need a smarter check here...
                enabled = True
        if not enabled:
            if check_perms:
                return self.patched.searchResults(REQUEST, **kw)
            else:
                return self.patched.unrestrictedSearchResults(REQUEST, **kw)

        if isinstance(REQUEST, dict):
            query = REQUEST.copy()
        else:
            query = {}
        query.update(kw)

        if check_perms:
            show_inactive = query.get('show_inactive', False)
            if isinstance(REQUEST, dict) and not show_inactive:
                show_inactive = 'show_inactive' in REQUEST

            user = _getAuthenticatedUser(self.catalogtool)
            query['allowedRolesAndUsers'] = \
                self.catalogtool._listAllowedRolesAndUsers(user)

            if not show_inactive and not _checkPermission(
                    AccessInactivePortalContent, self.catalogtool):
                query['effectiveRange'] = DateTime()
        orig_query = query.copy()
        # info('Running query: %s' % repr(orig_query))
        try:
            return self.search(query)
        except:
            info('Error running Query: %s\n%s' % (
                repr(orig_query),
                traceback.format_exc()))
            return self.patched.searchResults(REQUEST, **kw)

    def convertToElastic(self):
        setattr(self.catalogtool, CONVERTED_ATTR, True)
        self.catalogtool._p_changed = True
        properties = {}
        for name in self.catalog.indexes.keys():
            index = getIndex(self.catalog, name)
            if index is not None:
                properties[name] = index.create_mapping(name)
            else:
                raise Exception('Can not locate index for %s' % (
                    name))

        properties.update({
            'transaction': {'type': 'boolean'},
            'transaction_id': {
                'type': 'string',
                'index': 'not_analyzed',
                'store': False}
        })
        conn = self.connection
        try:
            conn.indices.create(self.index_name)
        except ElasticsearchException:
            pass

        mapping = {'properties': properties}
        conn.indices.put_mapping(
            doc_type=self.doc_type,
            body=mapping,
            index=self.index_name)

    @property
    def index_name(self):
        if hasattr(self.catalogtool, CUSTOM_INDEX_NAME_ATTR):
            return getattr(self.catalogtool, CUSTOM_INDEX_NAME_ATTR)
        return '-'.join(self.catalogtool.getPhysicalPath()[1:]).lower()

    @property
    def doc_type(self):
        return self.catalogtool.getId().lower()
