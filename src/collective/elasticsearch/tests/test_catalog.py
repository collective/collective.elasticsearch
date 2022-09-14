from collective.elasticsearch.hook import getHook
from collective.elasticsearch.testing import createObject
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.utils import getUID
from plone import api
from plone.app.contentrules.actions.move import MoveAction
from plone.app.contentrules.tests.dummy import DummyEvent
from plone.contentrules.rule.interfaces import IExecutable
from Products.CMFCore.indexing import processQueue
from zope.component import getMultiAdapter


EVENT_KLASS = "plone.app.event.dx.interfaces.IDXEvent"
DOCUMENT_KLASS = "plone.app.contenttypes.interfaces.IDocument"


class TestCatalog(BaseFunctionalTest):
    def remove_portal(self, value):
        portal_uid = getUID(api.portal.get())
        if portal_uid in value:
            del value[portal_uid]
        return value

    def get_hook(self):
        return getHook(es=self.es)

    def test_has_right_brain_data(self):
        current_length = len(self.catalog._catalog.uids)
        obj = createObject(self.portal, "Event", "event", title="Some Event")
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))
        self.assertEqual(self.get_hook().index, {getUID(obj): obj})
        self.portal.manage_delObjects(["event"])
        # uid not actually removed until this if catalog optimized
        processQueue()
        self.assertEqual(current_length, len(self.catalog._catalog.uids))
        # Plone 6 reindex the Portal here, so we remove it
        to_index = self.remove_portal(self.get_hook().index)
        self.assertEqual(self.get_hook().remove, {getUID(obj)})
        self.assertEqual(to_index, {})

    def test_rename_object(self):
        current_length = len(self.catalog._catalog.uids)
        obj = createObject(self.portal, "Event", "event1", title="Some Event")
        obj_uid = getUID(obj)
        self.assertEqual(current_length + 1, len(self.catalog._catalog.uids))
        api.content.rename(self.portal.event1, new_id="event2")
        # Plone 6 reindex the Portal here, so we remove it
        to_index = self.remove_portal(self.get_hook().index)
        self.assertEqual(self.get_hook().remove, set())
        self.assertEqual(to_index, {obj_uid: obj})

    def test_delete_object(self):
        obj = createObject(self.portal, "Event", "event_to_delete", title="Some Event")
        obj_uid = getUID(obj)
        self.portal.manage_delObjects(["event_to_delete"])
        processQueue()
        # Plone 6 reindex the Portal here, so we remove it
        to_index = self.remove_portal(self.get_hook().index)
        to_remove = self.get_hook().remove
        self.assertEqual(to_index, {})
        self.assertEqual(to_remove, {obj_uid})

    def test_change_position(self):
        folder = api.content.create(container=self.portal, type="Folder", id="folder")
        folder_uid = getUID(folder)

        for idx in range(1, 5):
            obj = api.content.create(
                container=folder, type="Document", id=f"document-{idx}"
            )
        # Move object to top
        folder.moveObjectsToTop(obj.id)
        processQueue()
        to_up_position = self.get_hook().positions
        self.assertIn(folder_uid, to_up_position)

    def test_moved_content(self):
        """content moved by content rules should remove the original catalog
        entry
        """
        target = api.content.create(container=self.portal, type="Folder", id="target")
        source = api.content.create(container=self.portal, type="Folder", id="source")
        e = MoveAction()
        e.target_folder = "/target"

        obj = api.content.create(container=source, type="Document", id="doc")
        ex = getMultiAdapter((target, e, DummyEvent(obj)), IExecutable)
        self.assertEqual(True, ex())
        catalog = api.portal.get_tool("portal_catalog")
        self.assertEqual(len(catalog(portal_type="Document", path="/plone/source")), 0)
        self.assertEqual(len(catalog(portal_type="Document", path="/plone/target")), 1)
