import threading
from logging import getLogger

from zope.interface import implementer
from transaction.interfaces import ISavepointDataManager, IDataManagerSavepoint

import transaction as transaction_manager

from pyes.exceptions import ElasticSearchException

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


def get():
    try:
        return tranaction_data.data
    except AttributeError:
        tranaction_data.data = TransactionData()
        return tranaction_data.data



@implementer(ISavepointDataManager)
class DataManager(object):

    def __init__(self, td):
        self.td = td
        self.savepoints = []

    def commit(self, trans):
        self.td.reset()

    def tpc_begin(self, trans):
        pass

    def tpc_vote(self, trans):
        pass

    def tpc_finish(self, trans):
        self.td.reset()

    def tpc_abort(self, trans):
        pass

    def abort(self, trans):
        try:
            self._abort(trans)
        except:
            # XXX log this better
            warn("Error aborting transaction")

    def _abort(self, trans):
        if self._active:
            td = self.td
            if len(td.docs) > 0:
                td.conn.refresh()
                self._revert(td.docs)
                td.conn.refresh()
                td.docs = []

    @property
    def _active(self):
        td = self.td
        if not td.registered:
            return False
        es = td.es
        if es.mode == DISABLE_MODE:
            return False
        if not td.conn:
            return False
        return True

    def _revert(self, docs):
        conn = self.td.conn
        es = self.td.es
        for action, uid, doc in reversed(docs):
            try:
                if action == Actions.add:
                    # if it was an add action, remove delete
                    conn.delete(es.catalogsid, es.catalogtype, uid)
                elif action in (Actions.modify, Actions.delete):
                    # if it was a modify or delete, restore the doc
                    conn.index(doc, es.catalogsid, es.catalogtype, uid)
            except ElasticSearchException, ex:
                # XXX log this better
                warn('There was an error cleaning up elastic transactions. '
                        'There could be inconsistencies')

    @property
    def savepoint(self):
        return self._savepoint

    def _savepoint(self):
        sp = Savepoint(self)
        self.savepoints.append(sp)
        return sp

    def should_retry(self, error):
        print 'should_retry'

    def sortKey(self):
        # Sort normally
        return "collective.elasticsearch"


@implementer(IDataManagerSavepoint)
class Savepoint:

    def __init__(self, dm):
        self.dm = dm
        self.index = len(dm.td.docs)

    def rollback(self):
        if not self.dm._active:
            return
        td = self.dm.td
        docs = td.docs[self.index:]
        td.conn.refresh()
        self.dm._revert(docs)
        td.conn.refresh()
        del td.docs[self.index:]


class TransactionData(object):

    def __init__(self):
        self.conn = None
        self.es = None
        self.registered = False
        self.docs = []

    def register(self, es):
        self.es = es
        self.registered = True
        # see if a transaction manager is not registered yet.
        transaction = transaction_manager.get()
        found = False
        for resource in transaction._resources:
            if isinstance(resource, DataManager):
                found = True
                break
        if not found:
            transaction.join(DataManager(self))

    def reset(self):
        self.docs = []
        self.es = None
        self.registered = False
        self.conn = None



