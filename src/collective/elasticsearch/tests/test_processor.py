from collective.elasticsearch.testing import ElasticSearch_FUNCTIONAL_TESTING
from collective.elasticsearch.testing import ElasticSearch_REDIS_TESTING
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.utils import getUID
from parameterized import parameterized_class
from plone import api
from plone.app.contentrules.actions.move import MoveAction
from plone.app.contentrules.tests.dummy import DummyEvent
from plone.app.testing import login
from plone.app.testing import TEST_USER_PASSWORD
from plone.contentrules.rule.interfaces import IExecutable
from Products.CMFCore.indexing import processQueue
from zope.component import getMultiAdapter


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestQueueProcessor(BaseFunctionalTest):
    def test_has_right_brain_data(self):
        processor = self.get_processor()
        current_length = len(self.catalog._catalog.uids)
        obj = api.content.create(self.portal, "Event", "event", title="Some Event")
        uuid = getUID(obj)
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))
        processQueue()
        actions = processor.actions
        self.assertIn(uuid, actions.index)
        self.portal.manage_delObjects(["event"])
        # uid not actually removed until this if catalog optimized
        processQueue()
        actions = processor.actions
        self.assertNotIn(uuid, actions.index)
        self.assertEqual(current_length, len(self.catalog._catalog.uids))
        self.assertIn(uuid, actions.unindex)

    def test_rename_object(self):
        processor = self.get_processor()
        current_length = len(self.catalog._catalog.uids)
        obj = api.content.create(self.portal, "Event", "event1", title="Some Event")
        obj_uid = getUID(obj)
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))
        api.content.rename(self.portal.event1, new_id="event2")
        self.assertIn(obj_uid, processor.actions.index)
        self.assertNotIn(obj_uid, processor.actions.unindex)

    def test_delete_object(self):
        processor = self.get_processor()
        obj = api.content.create(
            self.portal, "Event", "event_to_delete", title="Some Event"
        )
        obj_uid = getUID(obj)
        self.portal.manage_delObjects(["event_to_delete"])
        processQueue()
        self.assertIn(obj_uid, processor.actions.unindex)

    def test_moved_content(self):
        """content moved by content rules should remove the original catalog
        entry
        """
        processor = self.get_processor()
        target = api.content.create(container=self.portal, type="Folder", id="target")
        source = api.content.create(container=self.portal, type="Folder", id="source")
        e = MoveAction()
        e.target_folder = "/target"

        obj = api.content.create(container=source, type="Document", id="doc")
        obj_uid = getUID(obj)
        ex = getMultiAdapter((target, e, DummyEvent(obj)), IExecutable)
        self.assertEqual(True, ex())
        self.assertIn(obj_uid, processor.actions.index)

    def test_index_even_if_access_to_obj_might_be_restricted(self):
        processor = self.get_processor()
        user = api.user.create(
            username="worker",
            email="ordinary_person@example.com",
            password=TEST_USER_PASSWORD,
            roles=("Member",),
        )

        folder = api.content.create(self.portal, "Folder", "folder1", title="A folder")
        folder.manage_permission(
            "Access contents information", roles=["Manager"], acquire=False
        )
        obj = api.content.create(folder, "Event", "event1", title="Some Event")

        login(self.portal, user.getId())
        obj.reindexObject()
        processQueue()
        self.assertIn(obj.UID(), processor.actions.index)


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestRemoveIndexFromCatalog(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        # Create a content with the word fancy
        self.document = api.content.create(
            container=self.portal,
            type="Document",
            id="a-document",
            title="A Fancy Title",
        )
        # Force indexing in ES
        self.commit(wait=1)
        self.delete_es_only_indexes_from_catalog()

    def test_reindex_object(self):
        processor = self.get_processor()
        document = self.document
        document.title = "Common title"
        document.reindexObject(idxs=["SearchableText", "Title"])
        processQueue()
        actions = processor.actions
        uid = getUID(document)
        self.assertIn(uid, actions.reindex)
        self.assertIn("SearchableText", actions.reindex[uid])

        if self.layer == ElasticSearch_FUNCTIONAL_TESTING:
            self.assertIn("Common", actions.reindex[uid]["SearchableText"])
            self.assertIn("Title", actions.reindex[uid])
            self.assertIn("Common", actions.reindex[uid]["Title"])
        if self.layer == ElasticSearch_REDIS_TESTING:
            # There is a slight change in the API for redis. We do no extract
            # any data at this time.
            self.assertIsNone(actions.reindex[uid]["Title"])
            self.assertIsNone(actions.reindex[uid]["SearchableText"])
