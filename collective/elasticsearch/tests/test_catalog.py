from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.testing import createObject
import unittest2 as unittest


EVENT_KLASS = 'plone.app.event.dx.interfaces.IDXEvent'
DOCUMENT_KLASS = 'plone.app.contenttypes.interfaces.IDocument'


class TestQueries(BaseFunctionalTest):

    def test_has_right_brain_data(self):
        current_length = len(self.catalog._catalog.uids)
        createObject(self.portal, 'Event', 'event', title='Some Event')
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))
        self.portal.manage_delObjects(['event'])
        self.assertEqual(current_length, len(self.catalog._catalog.uids))


def test_suite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
