import random
import threading
from logging import getLogger
import traceback

import transaction
from transaction.interfaces import ISynchronizer
from transaction._transaction import Status
from zope.interface import implements

from pyes import (MatchAllQuery, TermFilter, FilteredQuery)
from pyes.exceptions import ElasticSearchException

from collective.elasticsearch.ejson import loads
from collective.elasticsearch.interfaces import DISABLE_MODE

logger = getLogger(__name__)
info = logger.info
warn = logger.warn


class Actions:
    add = 'add'
    modify = 'modify'
    delete = 'delete'


# let's use a thread local to store info on the elastic
# transaction since each request is done in it's own thread
tranaction_data = threading.local()


class TransactionData(object):

    def __init__(self):
        self.tid = random.randint(0, 9999999999)
        self.counter = 0
        self.conn = None
        self.es = None
        self.registered = False

    def register(self, es):
        self.es = es
        self.registered = True

    def reset(self, hard=False):
        self.tid = random.randint(0, 9999999999)
        self.counter = 0
        if hard:
            self.es = None
            self.registered = False
            self.conn = None


def get():
    try:
        return tranaction_data.data
    except AttributeError:
        tranaction_data.data = TransactionData()
        return tranaction_data.data


class Synchronizer(object):
    implements(ISynchronizer)

    def beforeCompletion(self, transaction):
        pass

    def afterCompletion(self, transaction):
        tdata = get()
        if not tdata.registered:
            return
        es = tdata.es
        if es.mode == DISABLE_MODE:
            tdata.reset()
            return

        success = transaction.status == Status.COMMITTED
        query = FilteredQuery(MatchAllQuery(),
            TermFilter('transaction_id', tdata.tid))
        
        conn = es.conn
        # NEED to refresh here otherwise we'll have inconsistencies
        conn.refresh()
        try:
            docs = conn.search(query, es.catalogsid, es.trns_catalogtype,
                               sort='order:desc')
            docs.count() # force executing
        except ElasticSearchException:
            # XXX uh oh, nasty, we have a problem. Let's log it.
            warn("Error trying to abort transaction: %s" %(
                traceback.format_exc()))
            tdata.reset()
            return

        for doc in docs:
            conn.delete(es.catalogsid, es.trns_catalogtype, doc.get_id())
            if not success:
                if doc.action == Actions.add:
                    # if it was an add action, remove delete
                    conn.delete(es.catalogsid, es.catalogtype, doc.uid)
                elif doc.action in (Actions.modify, Actions.delete):
                    # if it was a modify or delete, restore the doc
                    restored_doc = loads(doc.data)
                    conn.index(restored_doc, es.catalogsid, es.catalogtype, doc.uid)
        # NEED to refresh here otherwise we'll have inconsistencies
        conn.refresh()
        tdata.reset()

    def newTransaction(self, transaction):
        get().reset(True)


synchronizer = Synchronizer()
transaction.manager.registerSynch(synchronizer)
# setup the current transaction also...
if transaction.manager._txn is not None:
    transaction.get()._synchronizers.add(synchronizer)
