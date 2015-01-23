from collective.elasticsearch.tests import BaseTest
from collective.elasticsearch.testing import createObject
import unittest2 as unittest
from DateTime import DateTime
import time


EVENT_KLASS = 'plone.app.event.dx.interfaces.IDXEvent'
DOCUMENT_KLASS = 'plone.app.contenttypes.interfaces.IDocument'


class TestQueries(BaseTest):

    def test_field_index_query(self):
        createObject(self.portal, 'Event', 'event', title='Some Event')
        cat_results = self.searchResults(portal_type='Event')
        el_results = self.catalog(portal_type='Event')
        self.assertEqual(len(cat_results), len(el_results))
        self.assertEqual(len(cat_results), 1)

    def test_keyword_index_query(self):
        createObject(self.portal, 'Event', 'event', title='Some Event')
        cat_results = self.searchResults(object_provides=EVENT_KLASS)
        el_results = self.catalog(object_provides=[EVENT_KLASS])
        self.assertEqual(len(cat_results), len(el_results))
        self.assertEqual(len(cat_results), 1)

    def test_multi_keyword_index_query(self):
        createObject(self.portal, 'Event', 'event', title='Some Event')
        createObject(self.portal, 'Document', 'page', title='Some page')
        cat_results = self.searchResults(
            object_provides=[EVENT_KLASS, DOCUMENT_KLASS])
        el_results = self.catalog(
            object_provides=[EVENT_KLASS, DOCUMENT_KLASS])
        self.assertEqual(len(cat_results), len(el_results))
        self.assertEqual(len(cat_results), 2)

    def test_date_index_query(self):
        start = DateTime()
        time.sleep(1)
        events = []
        for idx in range(5):
            event = createObject(
                self.portal, 'Event',
                'event%i' % idx, title='Some Event %i' % idx)
            events.append(event)
        end = DateTime()
        query = {'query': (start, end), 'range': 'min:max'}
        cat_results = self.searchResults(created=query)
        el_results = self.catalog(created=query)
        self.assertEqual(len(cat_results), len(el_results))
        self.assertEqual(len(cat_results), len(events))

    def test_text_index_query(self):
        for idx in range(5):
            createObject(
                self.portal, 'Document',
                'page%i' % idx, title='Page %i' % idx)
            # should not show up in results
        events = []
        for idx in range(5):
            event = createObject(
                self.portal, 'Event',
                'event%i' % idx, title='Some Event %i' % idx)
            events.append(event)
        cat_results = self.searchResults(Title='Some Event')
        el_results = self.catalog(Title='Some Event')
        self.assertEqual(len(cat_results), len(el_results))
        self.assertEqual(len(cat_results), len(events))

        # only find one
        cat_results = self.searchResults(Title='Some Event 1',
                                         sort_on='getObjPositionInParent')
        el_results = self.catalog(Title='Some Event 1',
                                  sort_on='getObjPositionInParent')
        self.assertTrue('Some Event 1' in [
            b.Title for b in el_results])
        self.assertEqual(cat_results[0].Title, 'Some Event 1')

    def test_path_index_query(self):
        folder1 = createObject(self.portal, 'Folder', 'folder1',
                               title='Folder 1')
        createObject(folder1, 'Document', 'page1', title='Page 1')
        createObject(folder1, 'Document', 'page2', title='Page 2')
        createObject(folder1, 'Document', 'page3', title='Page 3')
        folder2 = createObject(folder1, 'Folder', 'folder2',
                               title='Folder 2')
        folder3 = createObject(folder2, 'Folder', 'folder3',
                               title='Folder 3')
        createObject(folder3, 'Document', 'page4', title='Page 4')
        createObject(folder3, 'Document', 'page5', title='Page 5')
        createObject(folder3, 'Document', 'page6', title='Page 6')
        self.assertEqual(
            len(self.catalog(path={'depth': 0, 'query': '/plone/folder1'})),
            len(self.searchResults(
                path={'depth': 0, 'query': '/plone/folder1'})))
        self.assertEqual(
            len(self.catalog(path={'depth': 1, 'query': '/plone/folder1'})),
            len(self.searchResults(path={'depth': 1,
                                         'query': '/plone/folder1'})))
        self.assertEqual(
            len(self.catalog(path={'depth': -1,
                                   'query': '/plone/folder1'})),
            len(self.searchResults(path={'depth': -1,
                                         'query': '/plone/folder1'})))
        self.assertEqual(
            len(self.catalog(path={'depth': 1, 'query': '/plone'})),
            len(self.searchResults(path={'depth': 1,
                                         'query': '/plone'})))
        self.assertEqual(
            len(self.catalog(path={'query': '/plone/folder1',
                                   'navtree_start': 2, 'navtree': 1},
                             is_default_page=False)),
            len(self.searchResults(path={'query': '/plone/folder1',
                                         'navtree_start': 2, 'navtree': 1},
                                   is_default_page=False)))

    def test_combined_query(self):
        createObject(self.portal, 'Folder', 'folder1', title='Folder 1')
        self.assertEqual(
            len(self.catalog(path={'depth': 1, 'query': '/plone'},
                             portal_type='Folder',
                             is_default_page=False)),
            1)

    def test_brains(self):
        event = createObject(self.portal, 'Event', 'event', title='Some Event')
        el_results = self.catalog(portal_type='Event')
        brain = el_results[0]
        self.assertEqual(brain.getObject(), event)
        self.assertEqual(brain.portal_type, 'Event')
        self.assertEqual(brain.getURL(), 'http://nohost/plone/event')
        self.assertEqual(brain.getPath(), '/plone/event')


def test_suite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
