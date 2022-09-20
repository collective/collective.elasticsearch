from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.utils import getUID
from plone import api
from plone.app.contentrules.actions.move import MoveAction
from plone.app.contentrules.tests.dummy import DummyEvent
from plone.contentrules.rule.interfaces import IExecutable
from Products.CMFCore.indexing import processQueue
from zope.component import getMultiAdapter


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


class TestMoveReindex(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        # Content on the Plone Site
        site_documents = []
        for idx in range(10):
            content = api.content.create(
                self.portal, "Document", f"document-{idx}", title=f"Page {idx}"
            )
            site_documents.append((content.id, getUID(content)))
        self.folder = api.content.create(
            container=self.portal, type="Folder", id="folder"
        )
        folder_documents = []
        for idx in range(10):
            content = api.content.create(
                self.folder, "Event", f"event-{idx}", title=f"Event {idx}"
            )
            folder_documents.append((content.id, getUID(content)))

        self.site_docs = site_documents
        self.folder_docs = folder_documents
        self.commit(wait=1)

    def test_change_position_site(self):
        processor = self.get_processor()
        portal = self.portal
        # Move last object to top
        doc_id, doc_uuid = self.site_docs[-1]
        portal.moveObjectsToTop(doc_id)
        processQueue()
        self.assertIn(doc_uuid, processor.actions.reindex)
        # Only reindex getObjPositionInParent
        idxs = list(processor.actions.reindex[doc_uuid].keys())
        self.assertEqual(len(idxs), 1)
        self.assertEqual(idxs[0], "getObjPositionInParent")

    def test_change_position_folder(self):
        processor = self.get_processor()
        folder = self.folder
        # Move last object to top
        doc_id, doc_uuid = self.folder_docs[-1]
        folder.moveObjectsToTop(doc_id)
        processQueue()
        self.assertIn(doc_uuid, processor.actions.reindex)
        # Only reindex getObjPositionInParent
        idxs = list(processor.actions.reindex[doc_uuid].keys())
        self.assertEqual(len(idxs), 1)
        self.assertEqual(idxs[0], "getObjPositionInParent")
