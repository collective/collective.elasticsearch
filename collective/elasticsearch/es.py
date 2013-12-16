from logging import getLogger
import traceback

from Acquisition import aq_base
from DateTime import DateTime
from Products.ZCatalog.Lazy import LazyMap
from Products.CMFCore.utils import _getAuthenticatedUser
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from zope.component import getUtility
from zope.component import queryMultiAdapter
from zope.component import ComponentLookupError

from plone.registry.interfaces import IRegistry
from plone.indexer.interfaces import IIndexableObject

from pyes.exceptions import IndexMissingException
from pyes import ES
from pyes.exceptions import (IndexAlreadyExistsException,
                             NotFoundException)

from collective.elasticsearch.brain import BrainFactory
from collective.elasticsearch.query import QueryAssembler
from collective.elasticsearch.interfaces import (
    IElasticSettings, DISABLE_MODE, DUAL_MODE)
from collective.elasticsearch.utils import getUID
from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch import td


logger = getLogger(__name__)
info = logger.info
warn = logger.warn

CONVERTED_ATTR = '_elasticconverted'


class PatchCaller(object):
    """
    Very odd I have to do this. If I don't,
    I get very pecular errors trying to call
    the original methods
    """

    def __init__(self, patched_object):
        self._patched_object = patched_object

    def __getattr__(self, name):
        """
        assuming original attribute has "__old_" prefix
        """
        if name[0] == '_':
            return self.__dict__[name]
        _type = type(aq_base(self._patched_object))
        func = getattr(_type, '__old_' + name)

        # "bind" it
        def bound_func(*args, **kwargs):
            return func(self._patched_object, *args, **kwargs)
        return bound_func


class ResultWrapper(object):
    """
    To cache a group of results that rolls.
    optimized for sequentially access
    """

    def __init__(self, rl, count=None, cache_size=1000, bulk_size=400):
        self.rl = rl
        if count is None:
            count = self.rl.count()
        if cache_size > count:
            cache_size = count
        if bulk_size > count:
            bulk_size = count
        if bulk_size > cache_size:
            cache_size = min(bulk_size * 2, count)
        self.cache_size = cache_size
        self.bulk_size = bulk_size
        self.iloc = lbound = 0
        # fill up the cache to start...
        self.cache = rl[lbound:self.cache_size]

    def __getitem__(self, val):
        lbound = self.iloc
        rbound = lbound + self.cache_size
        if isinstance(val, slice):
            if lbound <= val.start and rbound >= val.stop:
                start = val.start - lbound
                stop = val.stop - rbound
                return self.cache[start:stop]
            else:
                start = val.start
                end = val.stop
        else:
            if lbound <= val and rbound > val:
                return self.cache[val - self.iloc]
            else:
                start = end = val
        # grab a group, trimming off any that we need to...
        if start > (rbound - 1) or end > (rbound - 1):
            # in this case, we're adding to the end
            # chop off front
            self.cache = self.cache[self.bulk_size:]
            self.iloc += self.bulk_size
            additional = self.rl[rbound:rbound + self.bulk_size]
            if len(additional) == 0:
                raise IndexError
            # add to end
            self.cache.extend(additional)
        elif self.iloc > 0:
            # in this case, we're adding to front
            end = start
            start = min(self.iloc - self.bulk, 0)
            rcache = self.cache[end:]
            self.cache = self.rl[start:end]
            if len(self.cache) == 0:
                raise IndexError
            self.cache.extend(rcache)
        else:
            raise Exception("Error finding data")
        return self[val]

    def __len__(self):
        return len(self.rl)

    def __iter__(self):
        return self


class ElasticSearch(object):

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

        self.tdata = td.get()

    @property
    def catalog_converted(self):
        return getattr(self.catalogtool, CONVERTED_ATTR, False)

    @property
    def mode(self):
        if not self.catalog_converted:
            return DISABLE_MODE
        if self.registry is None:
            return DISABLE_MODE
        return self.registry.mode

    @property
    def bulk_size(self):
        try:
            return self.registry.bulk_size
        except:
            return 400

    @property
    def max_retries(self):
        try:
            return self.registry.max_retries
        except:
            return 3

    @property
    def timeout(self):
        try:
            return self.registry.timeout
        except:
            return 30.0

    @property
    def conn(self):
        if self.tdata.conn is None:
            self.tdata.conn = ES(
                self.registry.connection_string,
                bulk_size=self.bulk_size,
                max_retries=self.max_retries,
                timeout=self.timeout)
        return self.tdata.conn

    def query(self, query):
        qassembler = QueryAssembler(self.catalogtool)
        dquery, sort = qassembler.normalize(query)
        equery = qassembler(dquery)
        result = self.conn.search(equery, self.catalogsid, self.catalogtype,
                                  sort=sort, fields="path")
        count = result.count()
        result = ResultWrapper(result, count=count)
        factory = BrainFactory(self.catalog)
        return LazyMap(factory, result, count)

    def catalog_object(self, obj, uid=None, idxs=[],
                       update_metadata=1, pghandler=None):
        mode = self.mode
        if mode in (DISABLE_MODE, DUAL_MODE):
            result = self.patched.catalog_object(
                obj, uid, idxs, update_metadata, pghandler)
            if mode == DISABLE_MODE:
                return result
        wrapped_object = None
        if not IIndexableObject.providedBy(obj):
            # This is the CMF 2.2 compatible approach, which should be used
            # going forward
            wrapper = queryMultiAdapter((obj, self.catalogtool),
                                        IIndexableObject)
            if wrapper is not None:
                wrapped_object = wrapper
            else:
                wrapped_object = obj
        else:
            wrapped_object = obj
        conn = self.conn
        catalog = self.catalog
        if idxs == []:
            idxs = catalog.indexes.keys()
        index_data = {}
        for index_name in idxs:
            index = getIndex(catalog, index_name)
            if index is not None:
                value = index.get_value(wrapped_object)
                if value in (None, 'None'):
                    # yes, we'll index null data...
                    value = None
                index_data[index_name] = value
        if update_metadata:
            index = self.catalog.uids.get(uid, None)
            if index is None:  # we are inserting new data
                index = self.catalog.updateMetadata(obj, uid, None)
                self.catalog._length.change(1)
                self.catalog.uids[uid] = index
                self.catalog.paths[index] = uid
            # need to match elasticsearch result with brain
            self.catalog.updateMetadata(wrapped_object, uid, index)

        uid = getUID(obj)
        try:
            doc = conn.get(self.catalogsid, self.catalogtype, uid)
            self.registerInTransaction(uid, td.Actions.modify, doc)
        except NotFoundException:
            self.registerInTransaction(uid, td.Actions.add)
        conn.index(index_data, self.catalogsid, self.catalogtype, uid)
        if self.registry.auto_flush:
            conn.refresh()

    def registerInTransaction(self, uid, action, doc={}):
        if not self.tdata.registered:
            self.tdata.register(self)
        self.tdata.docs.append(
            (action, uid, doc)
        )

    def uncatalog_object(self, uid, obj=None, *args, **kwargs):
        mode = self.mode
        if mode in (DISABLE_MODE, DUAL_MODE):
            if self.catalog.uids.get(uid, None) is not None:
                result = self.patched.uncatalog_object(uid, *args, **kwargs)
            if mode == DISABLE_MODE:
                return result
        conn = self.conn

        uid = getUID(obj)
        try:
            doc = conn.get(self.catalogsid, self.catalogtype, uid)
            self.registerInTransaction(uid, td.Actions.delete, doc)
        except NotFoundException:
            pass
        try:
            conn.delete(self.catalogsid, self.catalogtype, uid)
        except NotFoundException:
            # already gone... Multiple calls?
            pass
        if self.registry.auto_flush:
            conn.refresh()

    def manage_catalogRebuild(self, REQUEST=None, RESPONSE=None):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.manage_catalogRebuild(REQUEST, RESPONSE)

        self.recreateCatalog()

        return self.patched.manage_catalogRebuild(REQUEST, RESPONSE)

    def manage_catalogClear(self, REQUEST=None, RESPONSE=None, URL1=None):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.manage_catalogClear(REQUEST, RESPONSE, URL1)

        self.recreateCatalog()

        if mode == DUAL_MODE:
            return self.patched.manage_catalogClear(REQUEST, RESPONSE, URL1)

    def refreshCatalog(self, clear=0, pghandler=None):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.refreshCatalog(clear, pghandler)

        return self.patched.refreshCatalog(clear, pghandler)

    def recreateCatalog(self):
        conn = self.conn
        try:
            conn.delete_index(self.catalogsid)
        except IndexMissingException:
            pass
        self.convertToElastic()

    def searchResults(self, REQUEST=None, check_perms=False, **kw):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.searchResults(REQUEST, **kw)
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
            return self.query(query)
        except:
            info("Error running Query: %s\n%s" % (
                repr(orig_query),
                traceback.format_exc()))
            if mode == DUAL_MODE:
                # fall back now...
                return self.patched.searchResults(REQUEST, **kw)
            else:
                return LazyMap(BrainFactory(self.catalog), [], 0)

    def convertToElastic(self):
        setattr(self.catalogtool, CONVERTED_ATTR, True)
        self.catalogtool._p_changed = True
        properties = {}
        for name in self.catalog.indexes.keys():
            index = getIndex(self.catalog, name)
            if index is not None:
                properties[name] = index.create_mapping(name)
            else:
                raise Exception("Can not locate index for %s" % (
                    name))

        conn = self.conn
        try:
            conn.create_index(self.catalogsid)
        except IndexAlreadyExistsException:
            pass

        mapping = {'properties': properties}
        conn.indices.put_mapping(
            doc_type=self.catalogtype,
            mapping=mapping,
            indices=[self.catalogsid])

    @property
    def catalogsid(self):
        return '-'.join(self.catalogtool.getPhysicalPath()[1:]).lower()

    @property
    def catalogtype(self):
        return self.catalogtool.getId().lower()
