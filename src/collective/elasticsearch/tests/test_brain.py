from collective.elasticsearch.result import ElasticSearchBrain
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.utils import get_settings
from Missing import MV
from plone import api

import transaction


class TestElasticSearchBrain(BaseFunctionalTest):
    """A record that only lives in elasticsearch is wrapped in an
    ElasticSearchBrain, which has to behave like a real catalog brain.
    """

    def setUp(self):
        super().setUp()
        page = api.content.create(self.portal, "Document", "page", title="Some Page")
        self.commit(wait=1)
        self.drop_catalog_entry(page)

    def drop_catalog_entry(self, obj):
        """Remove the ZODB catalog entry but keep the elasticsearch document.

        This is what content indexed straight into elasticsearch, without a
        counterpart in the ZODB catalog, looks like. The inner catalog is used
        on purpose, uncatalog_object on the tool would drop the elasticsearch
        document as well.
        """
        self.catalog._catalog.uncatalogObject("/".join(obj.getPhysicalPath()))
        transaction.commit()

    def get_brain(self):
        results = self.catalog(SearchableText="some page")
        self.assertEqual(len(results), 1, "Expected the elasticsearch only record")
        brain = results[0]
        self.assertIsInstance(
            brain,
            ElasticSearchBrain,
            "Records without a ZODB catalog entry must be elasticsearch brains",
        )
        return brain

    def test_indexed_value_is_returned(self):
        self.assertEqual(self.get_brain().Title, "Some Page")

    def test_metadata_column_without_value_is_missing_value(self):
        self.assertIn(
            "CreationDate",
            self.catalog.schema(),
            "Precondition: CreationDate is a metadata column",
        )
        self.assertIs(
            self.get_brain().CreationDate,
            MV,
            "A metadata column without a value must not raise an AttributeError",
        )

    def test_metadata_column_without_value_is_contained(self):
        brain = self.get_brain()
        self.assertIn(
            "CreationDate",
            brain,
            "A metadata column must be reported even without a value",
        )
        self.assertTrue(
            brain.has_key("CreationDate"),  # NOQA W601
            "has_key must agree with the containment check",
        )

    def test_indexed_value_is_contained(self):
        self.assertIn("SearchableText", self.get_brain())

    def test_unknown_name_is_not_contained(self):
        self.assertNotIn("no_such_column", self.get_brain())

    def test_unknown_name_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            self.get_brain().no_such_column

    def test_internal_name_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            self.get_brain()._v_no_such_column

    def test_item_access_returns_indexed_value(self):
        self.assertEqual(self.get_brain()["Title"], "Some Page")

    def test_item_access_of_metadata_column_without_value_is_missing_value(self):
        self.assertIs(self.get_brain()["CreationDate"], MV)

    def test_item_access_of_unknown_name_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.get_brain()["no_such_column"]

    def test_highlight_is_applied_to_the_description(self):
        settings = get_settings()
        settings.highlight = True
        settings.highlight_pre_tags = "<em>"
        settings.highlight_post_tags = "</em>"
        self.assertIn(
            "<em>",
            self.get_brain().Description,
            "Highlighting must reach brains of records without a catalog entry",
        )
