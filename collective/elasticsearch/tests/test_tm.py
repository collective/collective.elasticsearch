from collective.elasticsearch.tests import BaseTest
from collective.elasticsearch.testing import createObject
from collective.elasticsearch import td
import unittest2 as unittest
import transaction


class TestTransactions(BaseTest):

    def test_transaction_counter(self):
        tdata = td.get()
        createObject(self.portal, 'Event', 'event', title="Some Event")
        assert tdata.counter > 0
        prev = tdata.counter
        createObject(self.portal, 'Event', 'event2', title="Some Event")
        assert tdata.counter > prev

    def test_abort_td(self):
        tdata = td.get()
        createObject(self.portal, 'Event', 'event', title="Some Event")
        # query for it...
        cat_results = self.catalog(object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 1)

        transaction.abort()
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 0)
        self.assertEquals(tdata.counter, 0)

    def test_abort_deleting_item(self):
        tdata = td.get()
        createObject(self.portal, 'Event', 'event', title="Some Event")
        transaction.commit()
        # query for it...
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 1)

        # now delete
        self.portal.manage_delObjects(['event'])
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 0)

        # abort should now restore it to the index
        transaction.abort()
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 1)
        self.assertEquals(tdata.counter, 0)

    def test_modifying_item_then_abort(self):
        event = createObject(self.portal, 'Event', 'event', title="Some Event")
        transaction.commit()
        # query for it...
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 1)

        event.setTitle('Modified Event')
        event.reindexObject()

        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(cat_results[0].Title, 'Modified Event')

        transaction.abort()
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(cat_results[0].Title, 'Some Event')

    def test_adding_modifying_item_then_abort(self):
        event = createObject(self.portal, 'Event', 'event', title="Some Event")
        # query for it...
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 1)

        event.setTitle('Modified Event')
        event.reindexObject()

        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(cat_results[0].Title, 'Modified Event')

        transaction.abort()
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 0)

    def test_commit(self):
        tdata = td.get()
        createObject(self.portal, 'Event', 'event', title="Some Event")
        # query for it...
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 1)
        transaction.commit()
        cat_results = self.catalog(
            object_provides="Products.ATContentTypes.interfaces.event.IATEvent")
        self.assertEquals(len(cat_results), 1)
        self.assertEquals(tdata.counter, 0)


def test_suite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
