from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.tests import DIRECT_AND_REDIS_LAYERS
from parameterized import parameterized_class
from plone import api


@parameterized_class(DIRECT_AND_REDIS_LAYERS)
class TestElasticsearchRebuild(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        self.page = api.content.create(
            self.portal, "Document", "page", title="A Fancy Title"
        )
        self.commit(wait=1)

    def rebuild(self):
        self.es.rebuild_from_catalog()
        self.commit(wait=1)

    def test_document_deleted_from_elasticsearch_is_back_after_rebuild(self):
        self.es.connection.delete(index=self.es.index_name, id=self.page.UID())
        self.commit(wait=1)
        query = {"SearchableText": "fancy"}
        self.assertEqual(
            self.total_results(query), 0, "Precondition: the document must be gone"
        )
        self.rebuild()
        self.assertEqual(
            self.total_results(query), 1, "The rebuild must restore the document"
        )

    def test_rebuild_does_not_change_the_catalog(self):
        catalog_entries = len(self.catalog._catalog.uids)
        self.rebuild()
        self.assertEqual(
            len(self.catalog._catalog.uids),
            catalog_entries,
            "The rebuild must not touch the ZCatalog",
        )

    def test_rebuild_works_without_the_es_only_catalog_indexes(self):
        self.delete_es_only_indexes_from_catalog()
        self.rebuild()
        results = self.search({"SearchableText": "fancy"})
        self.assertEqual(
            [brain.getId for brain in results],
            ["page"],
            "SearchableText must be searchable in elasticsearch after the rebuild",
        )
