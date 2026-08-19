from collective.elasticsearch.result import ElasticSearchBrain
from collective.elasticsearch.tests import BaseFunctionalTest
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

    def test_unknown_name_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            self.get_brain().no_such_column

    def test_internal_name_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            self.get_brain()._v_no_such_column
