from collective.elasticsearch.testing import ElasticSearch_FUNCTIONAL_TESTING
from collective.elasticsearch.testing import ElasticSearch_REDIS_TESTING
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.utils import getESOnlyIndexes, get_settings
from DateTime import DateTime
from parameterized import parameterized
from parameterized import parameterized_class
from plone import api
from Products.ZCatalog.interfaces import ICatalogBrain


EVENT_KLASS = "plone.app.event.dx.interfaces.IDXEvent"
DOCUMENT_KLASS = "plone.app.contenttypes.interfaces.IDocument"


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestSearch(BaseFunctionalTest):

    event_klass = EVENT_KLASS
    document_klass = DOCUMENT_KLASS

    def test_field_index_query(self):
        api.content.create(self.portal, "Event", "event", title="Some Event")
        self.commit(wait=1)
        query = {"portal_type": "Event", "Title:": "some event"}
        self.assertEqual(self.total_results(query), 1)

    def test_keyword_index_query(self):
        api.content.create(self.portal, "Event", "event", title="Some Event")
        self.commit(wait=1)
        query = {"object_provides": [self.event_klass], "SearchableText": "Event"}
        self.assertEqual(self.total_results(query), 1)

    def test_multi_keyword_index_query(self):
        api.content.create(self.portal, "Event", "event", title="New Content")
        api.content.create(self.portal, "Document", "page", title="New Content")
        self.commit(wait=1)
        query = {
            "object_provides": [self.event_klass, self.document_klass],
            "SearchableText": "new content",
        }
        self.assertEqual(self.total_results(query), 2)

    def test_date_index_query(self):
        start = DateTime()
        events = []
        for idx in range(5):
            event = api.content.create(
                self.portal,
                "Event",
                f"event{idx}",
                title=f"Some Event {idx}",
                effective=DateTime("2015/09/25 20:00"),
            )
            events.append(event)
        self.commit(wait=1)
        end = DateTime()
        query = {
            "created": {
                "query": (start, end),
                "range": "minmax",
            },
            "portal_type": "Event",
        }
        cat_results = self.catalog._old_searchResults(**query)
        self.assertEqual(len(cat_results), self.total_results(query))
        self.assertEqual(len(cat_results), len(events))

        query = {
            "effective": {"query": DateTime().latestTime(), "range": "min"},
            "portal_type": "Event",
        }
        cat_results = self.catalog._old_searchResults(**query)
        self.assertEqual(len(cat_results), self.total_results(query))
        self.assertEqual(len(cat_results), 0)

        query = {
            "effective": {"query": DateTime().latestTime(), "range": "max"},
            "portal_type": "Event",
        }
        cat_results = self.catalog._old_searchResults(**query)
        self.assertEqual(len(cat_results), self.total_results(query))
        self.assertEqual(len(cat_results), 5)

    def test_text_index_query(self):
        for idx in range(5):
            api.content.create(
                self.portal, "Document", f"page{idx}", title=f"Page {idx}"
            )
            # should not show up in results
        events = []
        for idx in range(5):
            event = api.content.create(
                self.portal, "Event", f"event{idx}", title=f"Some Event {idx}"
            )
            events.append(event)

        self.commit(wait=1)

        query = {"Title": "Some Event"}
        self.assertEqual(self.total_results(query), len(events))

        query = {"Title": "Some Event 1", "sort_on": "getObjPositionInParent"}
        el_results = self.search(query)
        self.assertTrue("Some Event 1" in [b.Title for b in el_results])
        self.assertEqual(el_results[0].Title, "Some Event 1")

    def test_path_index_query(self):
        folder1 = api.content.create(
            self.portal, "Folder", "folder0", title="New Content 0"
        )
        for idx in range(1, 4):
            api.content.create(
                folder1, "Document", f"page{idx}", title=f"New Content {idx}"
            )
        folder2 = api.content.create(
            folder1, "Folder", "folder4", title="New Content 4"
        )
        folder3 = api.content.create(
            folder2, "Folder", "folder5", title="New Content 5"
        )
        for idx in range(6, 9):
            api.content.create(
                folder3, "Document", f"page{idx}", title=f"New Content {idx}"
            )

        self.commit(wait=1)
        query = {
            "path": {"depth": 0, "query": "/plone/folder0"},
            "SearchableText": "new content",
        }
        self.assertEqual(self.total_results(query), 1)
        query = {
            "path": {"depth": 1, "query": "/plone/folder0"},
            "SearchableText": "new content",
        }
        self.assertEqual(self.total_results(query), 4)
        query = {
            "path": {"depth": -1, "query": "/plone/folder0"},
            "SearchableText": "new content",
        }
        self.assertEqual(self.total_results(query), 9)
        query = {
            "path": {"depth": 1, "query": "/plone"},
            "SearchableText": "new content",
        }
        self.assertEqual(self.total_results(query), 1)
        # this proves its wrong
        query = {
            "path": {"query": "/plone/folder0", "navtree_start": 0, "navtree": 1},
            "is_default_page": False,
            "SearchableText": "new content",
        }
        self.assertEqual(self.total_results(query), 9)

    def test_combined_query(self):
        api.content.create(self.portal, "Folder", "folder1", title="Folder 1")
        self.commit(wait=1)
        query = {
            "path": {"depth": 1, "query": "/plone"},
            "portal_type": "Folder",
            "is_default_page": False,
            "SearchableText": "folder",
        }
        self.assertEqual(self.total_results(query), 1)

    def test_highlight_query(self):
        settings = get_settings()
        settings.highlight = True
        settings.highlight_pre_tags = '<em>'
        settings.highlight_post_tags = '</em>'
        api.content.create(self.portal,
                           "Document",
                           "page",
                           title="Some Page")
        self.commit(wait=1)
        query = {'SearchableText': 'some'}
        results = self.search(query)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].Description, "page <em>Some</em> Page")


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestBrains(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        self.event = api.content.create(
            self.portal, "Event", "event", title="Some Event"
        )
        self.commit(wait=1)

    def test_one_result_index_0(self):
        el_results = self.search({"portal_type": "Event", "Title": "Some Event"})
        self.assertEqual(len(el_results), 1)
        brain = el_results[0]
        self.assertEqual(brain.getObject(), self.event)
        self.assertEqual(brain.portal_type, "Event")
        self.assertEqual(brain.getURL(), self.event.absolute_url())
        self.assertEqual(brain.getPath(), "/plone/event")

    def test_one_result_index_last(self):
        el_results = self.search({"portal_type": "Event", "Title": "Some Event"})
        self.assertEqual(len(el_results), 1)
        brain = el_results[-1]
        self.assertEqual(brain.getObject(), self.event)
        self.assertEqual(brain.portal_type, "Event")
        self.assertEqual(brain.getURL(), self.event.absolute_url())
        self.assertEqual(brain.getPath(), "/plone/event")

    def test_two_results(self):
        api.content.create(self.portal, "Event", "event2", title="Some Event")
        self.commit(wait=1)

        el_results = self.search(
            {
                "portal_type": "Event",
                "Title": "Some Event",
                "sort_on": "getId",
                "sort_order": "descending",
            }
        )
        self.assertEqual(len(el_results), 2)
        brain = el_results[0]
        self.assertEqual(brain.getId, "event2")
        brain = el_results[1]
        self.assertEqual(brain.getId, "event")

        brain = el_results[-1]
        self.assertEqual(brain.getId, "event")
        brain = el_results[-2]
        self.assertEqual(brain.getId, "event2")


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestBrainsIndexing(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        for idx in range(120):
            api.content.create(
                self.portal, "Document", f"{idx:04d}page", title=f"Page {idx}"
            )
        self.commit(wait=1)
        self.el_results = self.search(
            {
                "portal_type": "Document",
                "sort_on": "getId",
                "sort_order": "asc",
            }
        )

    def test_all_indexed(self):
        self.assertEqual(len(self.el_results), 120)

    @parameterized.expand(
        [
            (0, "0000page"),
            (-1, "0119page"),
            (-50, "0070page"),
            (-55, "0065page"),
            (-100, "0020page"),
        ]
    )
    def test_ordering(self, result_idx, expected):
        self.assertEqual(self.el_results[result_idx].getId, expected)


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestCatalogRecordDeleted(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        zcatalog = self.catalog._catalog
        self.event = api.content.create(
            self.portal, "Event", "event-test", title="Gone Event"
        )
        self.commit(wait=1)
        path = "/".join(self.event.getPhysicalPath())
        zcatalog.uncatalogObject(path)
        self.commit()

    def test_search_results(self):
        el_results = self.search({"portal_type": "Event", "Title": "Gone Event"})
        self.assertEqual(len(el_results), 1)
        brain = el_results[0]
        self.assertTrue(ICatalogBrain.providedBy(brain))
        self.assertEqual(brain.getRID(), -1)
        # Test data from elastic will populate the brain
        self.assertEqual(brain.portal_type, "Event")
        self.assertEqual(brain.Title, "Gone Event")
        # Test
        self.assertEqual(brain.getPath(), "/plone/event-test")
        self.assertEqual(brain.getURL(), self.event.absolute_url())
        self.assertEqual(brain.getObject(), self.event)


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestDeleteObjectNotReflectedOnES(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        zcatalog = self.catalog._catalog
        self.event = api.content.create(
            self.portal, "Event", "event-test", title="Gone Event"
        )
        self.commit(wait=1)
        path = "/".join(self.event.getPhysicalPath())
        zcatalog.uncatalogObject(path)
        self.portal._delObject("event-test", suppress_events=True)
        self.commit()

    def test_search_results(self):
        el_results = self.search({"portal_type": "Event", "Title": "Gone Event"})
        self.assertEqual(len(el_results), 1)
        brain = el_results[0]
        self.assertTrue(ICatalogBrain.providedBy(brain))
        self.assertEqual(brain.getRID(), -1)
        # Test data from elastic will populate the brain
        self.assertEqual(brain.portal_type, "Event")
        self.assertEqual(brain.Title, "Gone Event")
        # Test
        self.assertEqual(brain.getPath(), "/plone/event-test")
        self.assertEqual(brain.getURL(), self.event.absolute_url())
        with self.assertRaises(KeyError):
            brain.getObject()


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestUncatalogRemoveOnES(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        self.event = api.content.create(
            self.portal, "Event", "event-test", title="Gone Event"
        )
        self.commit(wait=1)
        path = "/".join(self.event.getPhysicalPath())
        catalog = self.catalog
        catalog.uncatalog_object(path)
        self.commit(wait=1)

    def test_search_results(self):
        el_results = self.search({"portal_type": "Event", "Title": "Gone Event"})
        self.assertEqual(len(el_results), 0)


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestSearchOnRemovedIndex(BaseFunctionalTest):
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
        # Now delete the index from the catalog
        zcatalog = self.catalog._catalog
        # Delete indexes that should be only in ES
        idxs = getESOnlyIndexes()
        for idx in idxs:
            zcatalog.delIndex(idx)
        self.commit()

    def test_search_results(self):
        el_results = self.search({"portal_type": "Document", "SearchableText": "Fancy"})
        self.assertEqual(len(el_results), 1)
        self.assertEqual(el_results[0].getId, self.document.id)

    def test_search_results_after_reindex(self):
        # Update title
        document = self.document
        document.title = "Common title"
        document.reindexObject(idxs=["SearchableText", "Title"])
        self.commit(wait=1)
        # Search for the old title
        el_results = self.search({"portal_type": "Document", "SearchableText": "Fancy"})
        self.assertEqual(len(el_results), 0)
        # Search for the new title
        el_results = self.search(
            {"portal_type": "Document", "SearchableText": "Common"}
        )
        self.assertEqual(len(el_results), 1)
        self.assertEqual(el_results[0].getId, self.document.id)
