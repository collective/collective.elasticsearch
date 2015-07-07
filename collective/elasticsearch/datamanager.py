from logging import getLogger
import random
import string

from zope.interface import implementer
from transaction.interfaces import ISavepointDataManager, IDataManagerSavepoint

import transaction as transaction_manager

from elasticsearch.exceptions import NotFoundError
from collective.elasticsearch.interfaces import DISABLE_MODE
import traceback

logger = getLogger(__name__)
info = logger.info
warn = logger.warn


def _gen_trans_uid(uid, trans_id):
    return uid + '-transaction-' + trans_id


class Action(object):

    def __init__(self, uid, doc, dm):
        self.uid = uid
        self.doc = doc
        self.dm = dm

    @property
    def trans_uid(self):
        return _gen_trans_uid(self.uid, self.dm.transaction_id)

    def _index(self, index_data=None):
        es = self.dm.es
        if index_data is not None:
            self.doc.update(index_data)
        es.connection.index(
            index=es.index_name, doc_type=es.doc_type,
            id=self.trans_uid, body=dict(self.doc, **{
                'transaction': True,
                'transaction_id': self.dm.transaction_id
            }))

    initial = _index
    modify = _index

    def commit(self):
        '''
        bulk op, on commit
        '''
        doc = self.doc
        if 'transaction_id' in doc:
            del doc['transaction_id']
        doc['transaction'] = False
        return [{
            'index': {
                '_index': self.dm.es.index_name,
                '_type': self.dm.es.doc_type,
                '_id': self.uid
            }
        }, doc]

    def delete(self, index_data=None):
        es = self.dm.es
        es.connection.delete(index=es.index_name, doc_type=es.doc_type,
                             id=self.trans_uid)


class AddAction(Action):
    pass


class ModifyAction(Action):

    def initial(self, index_data=None):
        '''
        On initial, the doc will just be the index data because
        we haven't actually retrieved the whole doc
        '''
        es = self.dm.es
        conn = es.connection
        if self.uid in self.dm._cache:
            doc = self.dm._cache[self.uid]
        else:
            doc = conn.get(index=es.index_name, doc_type=es.doc_type, id=self.uid)['_source']
            self.dm._cache[self.uid] = doc
        doc.update(self.doc)
        self.doc = doc
        self._index()


class DeleteAction(Action):

    def initial(self, index_data=None):
        pass

    def modify(self, index_data=None):
        pass

    def commit(self):
        return [{
            'delete': {
                '_index': self.dm.es.index_name,
                '_type': self.dm.es.doc_type,
                '_id': self.uid
            }
        }]


class Actions:
    add = 'add'
    modify = 'modify'
    delete = 'delete'

    klass = {
        add: AddAction,
        modify: ModifyAction,
        delete: DeleteAction
    }


@implementer(ISavepointDataManager)
class ElasticDataManager(object):
    def __init__(self, es):
        self.savepoints = []
        self.actions = {}
        self.register(es)
        self._cache = {}
        self._exists_cache = {}

    def register(self, es):
        self.es = es
        self.transaction_id = ''.join(random.choice(
            string.letters + string.digits) for _ in range(10))

    def __contains__(self, uid):
        if uid in self.actions:
            return True
        for s in self.savepoints:
            if uid in s.actions:
                return True

    def keys(self):
        uids = []
        for s in self.savepoints:
            uids.extend(s.actions.keys())
        uids.extend(self.actions.keys())
        return list(set(uids))

    def __len__(self):
        '''
        how many current active objects
        '''
        return len(self.keys())

    def _get_closest_action(self, uid):
        if uid in self.actions:
            return self.actions[uid]
        for s in reversed(self.savepoints):
            if uid in s.actions:
                return s.actions[uid]

    def add_action(self, action_type, uid, index_data=None):
        if index_data is None:
            index_data = {}
        if uid in self:
            action_data = self._get_closest_action(uid)
            if action_type == Actions.delete:
                if action_data['action'] != Actions.delete:
                    # deleted an updated or created document
                    action = Actions.klass[action_data['action']](
                        uid, action_data['doc'], self)
                    action.delete()
                else:
                    # this case should never happen. If a document was deleted,
                    # it should really be deleted and it can't be deleted again
                    pass
            else:
                # use existing doc, and do modify action to modify existing data
                action = Actions.klass[action_type](uid, action_data['doc'], self)
                action.modify(index_data)
        else:
            action = Actions.klass[action_type](uid, index_data, self)
            action.initial()
        self.actions[uid] = {
            'action': action_type,
            'doc': action.doc
        }

    def reset(self):
        # delete the transaction data
        if self.es is not None and len(self.actions) > 0:
            try:
                self.es.connection.delete_by_query(
                    index=self.es.index_name,
                    doc_type=self.es.doc_type,
                    body={'query': {'filtered': {'filter': {
                          'and': [{'term': {'transaction': True}},
                                  {'term': {'transaction_id': self.transaction_id}}]},
                        'query': {'match_all': {}}}}
                    })
            except NotFoundError:
                # ignore if index not found. Might be test
                pass
        self.actions = {}
        self.savepoints = []
        self.es = None
        self._cache = {}
        self._exists_cache = {}

    def commit(self, trans):
        '''
        needs to commit ALL current transaction data AND savepoint data
        '''
        if not self._active or len(self) == 0:
            return self.reset()

        bulk_data = []
        es = self.es
        conn = es.connection

        for uid in self.keys():
            action_data = self._get_closest_action(uid)
            action = Actions.klass[action_data['action']](uid, action_data['doc'], self)
            bulk_data.extend(action.commit())
            if len(bulk_data) % self.es.get_setting('bulk_size', 50) == 0:
                conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)
                bulk_data = []
        if len(bulk_data) > 0:
            conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)
        if self.es.registry.auto_flush:
            self.es.connection.indices.refresh(index=self.es.index_name)
        self.reset()

    def tpc_begin(self, trans):
        pass

    def tpc_vote(self, trans):
        pass

    def tpc_finish(self, trans):
        self.reset()

    def tpc_abort(self, trans):
        pass

    def abort(self, trans):
        try:
            self._abort(trans)
        except:
            # XXX log this better
            warn('Error aborting transaction:\n%s' % traceback.format_exc())

    def _abort(self, trans):
        if self._active and len(self) > 0:
            self.reset()

    @property
    def _active(self):
        if self.es is None:
            return False
        if self.es.mode == DISABLE_MODE:
            return False
        return True

    def savepoint(self):
        # multiple savepoints stacked on each other
        # need to know about previous ones
        sp = Savepoint(self, self.actions)
        self.actions = {}
        self.savepoints.append(sp)
        return sp

    def should_retry(self, error):
        print 'should_retry'

    def sortKey(self):  # noqa
        # Sort normally
        return 'collective.elasticsearch'


@implementer(IDataManagerSavepoint)
class Savepoint:

    def __init__(self, dm, actions):
        self.dm = dm
        self.actions = actions

    def _get_closest_action(self, uid):
        for s in reversed(self.dm.savepoints):
            if uid in s.actions:
                return s.actions[uid]

    def rollback(self):
        if not self.dm._active:
            return
        es = self.dm.ds
        conn = es.connection

        # go through current transaction actions and compare
        # against this savepoints.

        savepoint_uids = []
        for s in self.dm.savepoints:
            savepoint_uids.extend(s.actions.keys())
        savepoint_uids = list(set(savepoint_uids))

        bulk_data = []
        for uid, dm_action in self.dm.actions.items():
            if uid in savepoint_uids:
                # if it's in an existing savepoint, we should be able to
                # safely reindex this doc. Here are the cases and reasons why
                # 1) if it's a delete action in active transaction,
                #    we know it was previously an update or add because
                #    you can not delete the same object twice.
                # 2) if add/modify in previous savepoint and also in
                #    current transaction, then we can just update the index
                #    we know it wasn't a delete previously because you can NOT
                #    add/modify a deleted object
                # therefor, just index the closest savepoint action object
                sp_action = self._get_closest_action(uid)
                bulk_data.extend([{
                    'index': {
                        '_index': es.index_name,
                        '_type': es.doc_type,
                        '_id': _gen_trans_uid(uid, self.dm.transaction_id)
                    }
                }, {
                    'doc': dict(sp_action['doc'], {
                        'transaction': True,
                        'transaction_id': self.dm.transaction_id
                    })
                }])
            elif dm_action['action'] != Actions.delete:
                # not in save point and it was an add/modify. Just delete it!
                bulk_data.append({'delete': {
                    '_index': es.index_name,
                    '_type': es.doc_type,
                    '_id': _gen_trans_uid(uid, self.dm.transaction_id)
                }})

            if len(bulk_data) % self.es.get_setting('bulk_size', 50) == 0:
                conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)
                bulk_data = []
        if len(bulk_data) > 0:
            conn.bulk(index=es.index_name, doc_type=es.doc_type, body=bulk_data)
        self.dm.savepoints.remove(self)
        self.dm.actions = self.actions  # now set active actions


def get_data_manager():
    transaction = transaction_manager.get()
    for resource in transaction._resources:
        if isinstance(resource, ElasticDataManager):
            if resource.es is None:
                return None
            return resource


def register_in_transaction(es):
    dm = get_data_manager()
    if dm is None:
        dm = ElasticDataManager(es)
        transaction = transaction_manager.get()
        transaction.join(dm)
    elif dm.es is None:
        dm.register(es)
    return dm
