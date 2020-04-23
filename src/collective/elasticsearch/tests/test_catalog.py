# -*- coding: utf-8 -*-
try:
    from Products.CMFCore.indexing import processQueue
except ImportError:
    # BBB processQueue does not exist in Plone 5.0 and earlier
    def processQueue():
        pass
from collective.elasticsearch.hook import getHook
from collective.elasticsearch.testing import HAS_ATCONTENTTYPES
from collective.elasticsearch.testing import createObject
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.utils import getUID
from plone import api
from plone.app.contentrules.actions.move import MoveAction
from plone.app.contentrules.tests.dummy import DummyEvent
from plone.contentrules.rule.interfaces import IExecutable
from zope.component import getMultiAdapter

import unittest2 as unittest

EVENT_KLASS = 'plone.app.event.dx.interfaces.IDXEvent'
DOCUMENT_KLASS = 'plone.app.contenttypes.interfaces.IDocument'


class TestQueries(BaseFunctionalTest):

    def get_hook(self):
        return getHook(es=self.es)

    def test_has_right_brain_data(self):
        current_length = len(self.catalog._catalog.uids)
        obj = createObject(self.portal, 'Event', 'event', title='Some Event')
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))
        self.assertEqual(self.get_hook().index, {getUID(obj): obj})
        self.portal.manage_delObjects(['event'])
        # uid not actually removed until this if catalog optimized
        processQueue()
        self.assertEqual(current_length, len(self.catalog._catalog.uids))
        self.assertEqual(self.get_hook().remove, {getUID(obj)})
        self.assertEqual(self.get_hook().index, {})

    def test_rename_object(self):
        current_length = len(self.catalog._catalog.uids)
        obj = createObject(self.portal, 'Event', 'event1', title='Some Event')
        obj_uid = getUID(obj)
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))
        api.content.rename(self.portal.event1, new_id='event2')
        self.assertEqual(self.get_hook().remove, set())
        self.assertEqual(self.get_hook().index, {obj_uid: obj})

    def test_delete_object(self):
        obj = createObject(
            self.portal,
            'Event',
            'event_to_delete',
            title='Some Event')
        obj_uid = getUID(obj)
        self.portal.manage_delObjects(['event_to_delete'])
        processQueue()
        self.assertEqual(self.get_hook().index, {})
        self.assertEqual(self.get_hook().remove, {obj_uid})

    def test_moved_content(self):
        """ content moved by content rules should remove the original catalog
            entry
        """
        target = api.content.create(
            container=self.portal, type='Folder', id='target')
        source = api.content.create(
            container=self.portal, type='Folder', id='source')
        e = MoveAction()
        e.target_folder = '/target'

        obj = api.content.create(container=source, type='Document', id='doc')
        ex = getMultiAdapter((target, e, DummyEvent(obj)), IExecutable)
        self.assertEqual(True, ex())
        catalog = api.portal.get_tool('portal_catalog')
        self.assertEqual(
            len(catalog(portal_type='Document', path='/plone/source')), 0)
        self.assertEqual(
            len(catalog(portal_type='Document', path='/plone/target')), 1)


if HAS_ATCONTENTTYPES:
    from collective.elasticsearch.testing import ElasticSearch_FUNCTIONAL_TESTING_AT  # noqa

    class TestQueriesAT(TestQueries):
        layer = ElasticSearch_FUNCTIONAL_TESTING_AT


def test_suite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
