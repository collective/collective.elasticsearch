# -*- coding: utf-8 -*-
from collective.elasticsearch import hook, logger
from collective.elasticsearch.brain import BrainFactory
from collective.elasticsearch.interfaces import (IElasticSearchCatalog,
                                                 IElasticSettings,
                                                 IMappingProvider,
                                                 IQueryAssembler)
from collective.elasticsearch.utils import getESOnlyIndexes
from DateTime import DateTime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from plone import api
from plone.registry.interfaces import IRegistry
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission, _getAuthenticatedUser
from Products.ZCatalog.Lazy import LazyMap
from zope.component import ComponentLookupError, getMultiAdapter, getUtility
from zope.globalrequest import getRequest
from zope.interface import implementer


CONVERTED_ATTR = '_elasticconverted'
CUSTOM_INDEX_NAME_ATTR = '_elasticcustomindex'
INDEX_VERSION_ATTR = '_elasticindexversion'


def _reversed_sort(sort):
    criterion, order = sort.split(':')
    if order == 'desc':
        order = 'asc'
    elif order == 'asc':
        order = 'desc'
    else:
        raise ValueError("Invalid order: %s" % order)

    return "%s:%s" % (criterion, order)


class ElasticResult(object):

    def __init__(self, es, query, **query_params):
        assert 'sort' not in query_params
        assert 'start' not in query_params
        self.es = es
        self.bulk_size = es.get_setting('bulk_size', 50)
        qassembler = getMultiAdapter((getRequest(), es), IQueryAssembler)
        dquery, sort = qassembler.normalize(query)
        equery = qassembler(dquery)

        # results are stored in a dictionary, keyed
        # but the start index of the bulk size for the
        # results it holds. This way we can skip around
        # for result data in a result object
        self.query = equery
        result = es._search(self.query, sort=sort, **query_params)['hits']
        self.results = {
            0: result['hits']
        }
        self.count = result['total']
        self.sort = sort
        self.query_params = query_params

    def __getitem__(self, key):
        if isinstance(key, slice):
            return [self[i] for i in range(key.start, key.end)]
        else:
            if key + 1 > self.count:
                raise IndexError
            elif key < 0 and abs(key) > self.count:
                raise IndexError
            elif key >= 0:
                result_key = (key / self.bulk_size) * self.bulk_size
                start = result_key
                sort = self.sort
                result_index = key % self.bulk_size
            elif key < 0:
                result_key = - ((abs(key) / self.bulk_size) * self.bulk_size) - 1  # noqa
                start = abs(result_key) - 1
                sort = _reversed_sort(self.sort)
                result_index = (abs(key) - 1) % self.bulk_size

            if result_key not in self.results:
                self.results[result_key] = self.es._search(
                    self.query, sort=sort, start=start, **self.query_params
                )['hits']['hits']

            return self.results[result_key][result_index]


@implementer(IElasticSearchCatalog)
class ElasticSearchCatalog(object):
    '''
    from patched methods
    '''

    def __init__(self, catalogtool):
        self.catalogtool = catalogtool
        self.catalog = catalogtool._catalog

        try:
            registry = getUtility(IRegistry)
            try:
                self.registry = registry.forInterface(
                    IElasticSettings,
                    check=False
                )
            except Exception:
                self.registry = None
        except ComponentLookupError:
            self.registry = None

        self._conn = None

    @property
    def connection(self):
        if self._conn is None:
            kwargs = dict()
            if self.get_setting('timeout', 0):
                kwargs['timeout'] = self.get_setting('timeout')
            if self.get_setting('sniff_on_start', False):
                kwargs['sniff_on_start'] = True
            if self.get_setting('sniff_on_connection', False):
                kwargs['sniff_on_connection'] = True
            if self.get_setting('sniffer_timeout', 0):
                kwargs['sniffer_timeout'] = self.get_setting('sniffer_timeout')
            if self.get_setting('retry_on_timeout', False):
                kwargs['retry_on_timeout'] = True
            self._conn = Elasticsearch(
                self.registry.hosts,
                **kwargs
            )
        return self._conn

    def _search(self, query, **query_params):
        '''
        '''
        if 'start' in query_params:
            query_params['from_'] = query_params.pop('start')

        query_params['fields'] = query_params.get('fields', 'path.path')
        query_params['size'] = self.get_setting('bulk_size', 50)

        return self.connection.search(index=self.index_name,
                                      doc_type=self.doc_type,
                                      body={'query': query},
                                      **query_params)

    def search(self, query, factory=None, **query_params):
        """
        @param query: dict
            The plone query
        @param factory: function(result: dict): any
            The factory that maps each elastic search result.
            By default, get the plone catalog brain.
        @param query_params:
            Parameters to pass to the search method
            'fields': the list of fields to get from stored source
        @return: LazyMap
        """
        result = ElasticResult(self, query, **query_params)
        if not factory:
            factory = BrainFactory(self.catalog)
        return LazyMap(factory, result, result.count)

    @property
    def catalog_converted(self):
        return getattr(self.catalogtool, CONVERTED_ATTR, False)

    @property
    def enabled(self):
        return (
            self.registry and
            self.registry.enabled and
            self.catalog_converted
        )

    def get_setting(self, name, default=None):
        return getattr(self.registry, name, default)

    def catalog_object(self, obj, uid=None, idxs=[], update_metadata=1,
                       pghandler=None):
        if idxs != ['getObjPositionInParent']:
            self.catalogtool._old_catalog_object(
                obj, uid, idxs, update_metadata, pghandler)

        if not self.enabled:
            return
        hook.add_object(self, obj)

    def uncatalog_object(self, uid, obj=None, *args, **kwargs):
        # always need to uncatalog to remove brains, etc
        if obj is None:
            # with archetypes, the obj is not passed, only the uid is
            try:
                obj = api.content.get(uid)
            except KeyError:
                pass

        result = self.catalogtool._old_uncatalog_object(uid, *args, **kwargs)
        if self.enabled:
            hook.remove_object(self, obj)

        return result

    def manage_catalogRebuild(self, *args, **kwargs):
        if self.enabled:
            self.recreateCatalog()
        return self.catalogtool._old_manage_catalogRebuild(*args, **kwargs)

    def manage_catalogClear(self, *args, **kwargs):
        if self.enabled:
            self.recreateCatalog()

        return self.catalogtool._old_manage_catalogClear(*args, **kwargs)

    def recreateCatalog(self):
        conn = self.connection
        try:
            conn.indices.delete(index=self.real_index_name)
        except NotFoundError:
            pass
        if self.index_version:
            try:
                conn.indices.delete_alias(
                    self.index_name,
                    self.real_index_name)
            except NotFoundError:
                pass
        self.convertToElastic()

    def searchResults(self, REQUEST=None, check_perms=False, **kw):
        enabled = False
        if self.enabled:
            # need to also check if it is a search result we care about
            # using EL for
            if getESOnlyIndexes().intersection(kw.keys()):
                enabled = True
        if not enabled:
            if check_perms:
                return self.catalogtool._old_searchResults(REQUEST, **kw)
            else:
                return self.catalogtool._old_unrestrictedSearchResults(
                    REQUEST,
                    **kw)

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
        logger.debug('Running query: %s' % repr(orig_query))
        try:
            return self.search(query)
        except Exception:
            logger.exception('Error running Query: {0!r}'.format(orig_query))
            return self.catalogtool._old_searchResults(REQUEST, **kw)

    def convertToElastic(self):
        setattr(self.catalogtool, CONVERTED_ATTR, True)
        self.catalogtool._p_changed = True
        adapter = getMultiAdapter((getRequest(), self), IMappingProvider)
        mapping = adapter()
        self.connection.indices.put_mapping(
            doc_type=self.doc_type,
            body=mapping,
            index=self.index_name)

    @property
    def index_name(self):
        if hasattr(self.catalogtool, CUSTOM_INDEX_NAME_ATTR):
            return getattr(self.catalogtool, CUSTOM_INDEX_NAME_ATTR)
        return '-'.join(self.catalogtool.getPhysicalPath()[1:]).lower()

    @property
    def index_version(self):
        return getattr(self.catalogtool, INDEX_VERSION_ATTR, None)

    def bump_index_version(self):
        version = getattr(self.catalogtool, INDEX_VERSION_ATTR, None)
        if version is None:
            version = 1
        else:
            version += 1
        setattr(self.catalogtool, INDEX_VERSION_ATTR, version)
        return version

    @property
    def real_index_name(self):
        if self.index_version:
            return '%s_%i' % (self.index_name, self.index_version)
        return self.index_name

    @property
    def doc_type(self):
        return self.catalogtool.getId().lower()
