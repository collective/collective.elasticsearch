from collective.elasticsearch.tests import BaseTest
from collective.elasticsearch.testing import createObject
from collective.elasticsearch import datamanager
import unittest2 as unittest
import transaction


EVENT_KLASS = 'plone.app.event.dx.interfaces.IDXEvent'


class TestTransactions(BaseTest):

    def test_transaction_counter(self):
        createObject(self.portal, 'Event', 'event', title='Some Event')
        dm = datamanager.get_data_manager()
        assert len(dm) > 0
        prev = len(dm)
        createObject(self.portal, 'Event', 'event2', title='Some Event')
        assert len(dm) > prev

    def test_abort_dm(self):
        createObject(self.portal, 'Event', 'event', title='Some Event')
        # query for it...
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 1)

        transaction.abort()
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 0)

        dm = datamanager.get_data_manager()
        self.assertEqual(len(dm), 0)

    def test_abort_deleting_item(self):
        createObject(self.portal, 'Event', 'event', title='Some Event')
        transaction.commit()
        # query for it...
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 1)

        # now delete
        self.portal.manage_delObjects(['event'])
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 0)

        # abort should now restore it to the index
        transaction.abort()
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 1)

        dm = datamanager.get_data_manager()
        self.assertEqual(len(dm), 0)
        self.portal.manage_delObjects(['event'])
        transaction.commit()

    def test_modifying_item_then_abort(self):
        event = createObject(self.portal, 'Event', 'event', title='Some Event')
        transaction.commit()
        # query for it...
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 1)

        event.setTitle('Modified Event')
        event.reindexObject()

        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(cat_results[0].Title, 'Modified Event')

        transaction.abort()
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(cat_results[0].Title, 'Some Event')
        self.portal.manage_delObjects(['event'])
        transaction.commit()

    def test_adding_modifying_item_then_abort(self):
        event = createObject(self.portal, 'Event', 'event', title='Some Event')
        # query for it...
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 1)

        event.setTitle('Modified Event')
        event.reindexObject()

        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(cat_results[0].Title, 'Modified Event')

        transaction.abort()
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 0)

    def test_commit(self):
        createObject(self.portal, 'Event', 'event', title='Some Event')
        # query for it...
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 1)
        transaction.commit()
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 1)

        dm = datamanager.get_data_manager()
        self.assertEqual(len(dm), 0)
        self.portal.manage_delObjects(['event'])
        transaction.commit()

    def test_deleting_multiple_items_works_with_result_set(self):
        createObject(self.portal, 'Event', 'event1', title='Some Event')
        createObject(self.portal, 'Event', 'event2', title='Some Event')
        transaction.commit()
        # query for it...
        cat_results = self.catalog(object_provides=EVENT_KLASS)
        self.assertEqual(len(cat_results), 2)

        # now delete
        self.portal.manage_delObjects(['event1'])
        # should still be able to access second of query result
        self.assertTrue(cat_results[1] is not None)
        self.portal.manage_delObjects(['event2'])
        transaction.commit()


def test_suite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
