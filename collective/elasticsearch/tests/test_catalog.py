from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.testing import createObject
from collective.elasticsearch.testing import HAS_ATCONTENTTYPES

import unittest2 as unittest
from plone import api

EVENT_KLASS = 'plone.app.event.dx.interfaces.IDXEvent'
DOCUMENT_KLASS = 'plone.app.contenttypes.interfaces.IDocument'


class TestQueries(BaseFunctionalTest):

    def test_has_right_brain_data(self):
        current_length = len(self.catalog._catalog.uids)
        createObject(self.portal, 'Event', 'event', title='Some Event')
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))
        self.portal.manage_delObjects(['event'])
        self.assertEqual(current_length, len(self.catalog._catalog.uids))

    def test_rename_object(self):
        current_length = len(self.catalog._catalog.uids)
        createObject(self.portal, 'Event', 'event1', title='Some Event')
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))
        api.content.rename(self.portal.event1, new_id='event2')
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))


if HAS_ATCONTENTTYPES:
    from collective.elasticsearch.testing import ElasticSearch_FUNCTIONAL_TESTING_AT

    class TestQueriesAT(TestQueries):

        layer = ElasticSearch_FUNCTIONAL_TESTING_AT


def test_suite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
