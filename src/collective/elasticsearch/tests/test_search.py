from collective.elasticsearch.testing import createObject
from collective.elasticsearch.tests import BaseFunctionalTest
from DateTime import DateTime

import time


EVENT_KLASS = "plone.app.event.dx.interfaces.IDXEvent"
DOCUMENT_KLASS = "plone.app.contenttypes.interfaces.IDocument"


class TestSearch(BaseFunctionalTest):
    event_klass = EVENT_KLASS
    document_klass = DOCUMENT_KLASS

    def test_field_index_query(self):
        createObject(self.portal, "Event", "event", title="Some Event")
        self.commit()
        self.es.connection.indices.flush()
        time.sleep(1)
        el_results = self.catalog(portal_type="Event", Title="some event")
        self.assertEqual(len(el_results), 1)

    def test_keyword_index_query(self):
        createObject(self.portal, "Event", "event", title="Some Event")
        self.commit()
        self.es.connection.indices.flush()
        time.sleep(1)
        el_results = self.catalog(
            object_provides=[self.event_klass], SearchableText="Event"
        )
        self.assertEqual(len(el_results), 1)

    def test_multi_keyword_index_query(self):
        createObject(self.portal, "Event", "event", title="New Content")
        createObject(self.portal, "Document", "page", title="New Content")
        self.commit()
        self.es.connection.indices.flush()
        time.sleep(1)
        el_results = self.catalog(
            object_provides=[self.event_klass, self.document_klass],
            SearchableText="new content",
        )
        self.assertEqual(len(el_results), 2)

    def test_date_index_query(self):
        start = DateTime()
        time.sleep(1)
        events = []
        for idx in range(5):
            event = createObject(
                self.portal,
                "Event",
                f"event{idx}",
                title=f"Some Event {idx}",
                effective=DateTime("2015/09/25 20:00"),
            )
            events.append(event)

        self.commit()
        self.es.connection.indices.flush()

        end = DateTime()
        query = {
            "created": {
                "query": (start, end),
                "range": "minmax",
            },
            "portal_type": "Event",
        }
        cat_results = self.catalog._old_searchResults(**query)
        el_results = self.catalog(**query)
        self.assertEqual(len(cat_results), len(el_results))
        self.assertEqual(len(cat_results), len(events))

        query = {"query": DateTime().latestTime(), "range": "min"}
        cat_results = self.catalog._old_searchResults(
            effective=query, portal_type="Event"
        )
        el_results = self.catalog(effective=query, portal_type="Event")
        self.assertEqual(len(cat_results), len(el_results))
        self.assertEqual(len(cat_results), 0)

        query = {"query": DateTime().latestTime(), "range": "max"}
        cat_results = self.catalog._old_searchResults(
            effective=query, portal_type="Event"
        )
        el_results = self.catalog(effective=query, portal_type="Event")
        self.assertEqual(len(cat_results), len(el_results))
        self.assertEqual(len(cat_results), 5)

    def test_text_index_query(self):
        for idx in range(5):
            createObject(self.portal, "Document", f"page{idx}", title=f"Page {idx}")
            # should not show up in results
        events = []
        for idx in range(5):
            event = createObject(
                self.portal, "Event", f"event{idx}", title=f"Some Event {idx}"
            )
            events.append(event)

        self.commit()
        self.es.connection.indices.flush()
        time.sleep(1)

        el_results = self.catalog(Title="Some Event")
        self.assertEqual(len(el_results), len(events))

        el_results = self.catalog(
            Title="Some Event 1", sort_on="getObjPositionInParent"
        )
        self.assertTrue("Some Event 1" in [b.Title for b in el_results])
        self.assertEqual(el_results[0].Title, "Some Event 1")

    def test_path_index_query(self):
        folder1 = createObject(self.portal, "Folder", "folder0", title="New Content 0")
        createObject(folder1, "Document", "page1", title="New Content 1")
        createObject(folder1, "Document", "page2", title="New Content 2")
        createObject(folder1, "Document", "page3", title="New Content 3")
        folder2 = createObject(folder1, "Folder", "folder4", title="New Content 4")
        folder3 = createObject(folder2, "Folder", "folder5", title="New Content 5")
        createObject(folder3, "Document", "page6", title="New Content 6")
        createObject(folder3, "Document", "page7", title="New Content 7")
        createObject(folder3, "Document", "page8", title="New Content 8")

        self.commit()
        self.es.connection.indices.flush()
        time.sleep(1)

        self.assertEqual(
            len(
                self.catalog(
                    path={"depth": 0, "query": "/plone/folder0"},
                    SearchableText="new content",
                )
            ),
            1,
        )
        self.assertEqual(
            len(
                self.catalog(
                    path={"depth": 1, "query": "/plone/folder0"},
                    SearchableText="new content",
                )
            ),
            4,
        )
        self.assertEqual(
            len(
                self.catalog(
                    path={"depth": -1, "query": "/plone/folder0"},
                    SearchableText="new content",
                )
            ),
            9,
        )
        self.assertEqual(
            len(
                self.catalog(
                    path={"depth": 1, "query": "/plone"}, SearchableText="new content"
                )
            ),
            1,
        )
        # this proofs its wrong
        self.assertEqual(
            len(
                self.catalog(
                    path={"query": "/plone/folder0", "navtree_start": 0, "navtree": 1},
                    is_default_page=False,
                    SearchableText="new content",
                )
            ),
            9,
        )

    def test_combined_query(self):
        createObject(self.portal, "Folder", "folder1", title="Folder 1")
        self.commit()
        self.es.connection.indices.flush()
        time.sleep(1)
        self.assertEqual(
            len(
                self.catalog(
                    path={"depth": 1, "query": "/plone"},
                    portal_type="Folder",
                    is_default_page=False,
                    SearchableText="folder",
                )
            ),
            1,
        )

    def test_brains(self):
        event = createObject(self.portal, "Event", "event", title="Some Event")
        self.commit()
        self.es.connection.indices.flush()
        time.sleep(1)
        el_results = self.catalog(portal_type="Event", Title="Some Event")
        self.assertEqual(len(el_results), 1)
        brain = el_results[0]
        self.assertEqual(brain.getObject(), event)
        self.assertEqual(brain.portal_type, "Event")
        self.assertEqual(brain.getURL(), "http://nohost/plone/event")
        self.assertEqual(brain.getPath(), "/plone/event")

        brain = el_results[-1]
        self.assertEqual(brain.getObject(), event)
        self.assertEqual(brain.portal_type, "Event")
        self.assertEqual(brain.getURL(), "http://nohost/plone/event")
        self.assertEqual(brain.getPath(), "/plone/event")

        createObject(self.portal, "Event", "event2", title="Some Event")
        self.commit()
        self.es.connection.indices.flush()
        time.sleep(1)

        el_results2 = self.catalog(
            portal_type="Event",
            Title="Some Event",
            sort_on="getId",
            sort_order="descending",
        )
        self.assertEqual(len(el_results2), 2)
        brain = el_results2[0]
        self.assertEqual(brain.getId, "event2")
        brain = el_results2[1]
        self.assertEqual(brain.getId, "event")

        brain = el_results2[-1]
        self.assertEqual(brain.getId, "event")
        brain = el_results2[-2]
        self.assertEqual(brain.getId, "event2")

    def test_brains_indexing(self):
        for idx in range(120):
            createObject(self.portal, "Document", f"{idx:04d}page", title=f"Page {idx}")
        self.commit()
        el_results = self.catalog(
            portal_type="Document", sort_on="getId", sort_order="asc"
        )
        self.assertEqual(len(el_results), 120)
        self.assertEqual(el_results[0].getId, "0000page")
        self.assertEqual(el_results[-1].getId, "0119page")
        self.assertEqual(el_results[-50].getId, "0070page")
        self.assertEqual(el_results[-55].getId, "0065page")
        self.assertEqual(el_results[-100].getId, "0020page")
