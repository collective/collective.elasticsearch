from collective.elasticsearch.testing import ElasticSearch_FUNCTIONAL_TESTING
from collective.elasticsearch.testing import ElasticSearch_NO_SEARCH_PATCHES_TESTING
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.utils import getESOnlyIndexes
from DateTime import DateTime
from parameterized import parameterized_class
from plone import api
from plone.app.testing import logout


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_NO_SEARCH_PATCHES_TESTING},
    ]
)
class TestSecureSearch(BaseFunctionalTest):
    def create_expired_page(self):
        page = api.content.create(self.portal, "Document", "page", title="Expired Page")
        page.setExpirationDate(DateTime() - 1)
        page.reindexObject()
        self.commit(wait=1)
        return page

    def test_anonymous_does_not_find_private_content(self):
        page = api.content.create(self.portal, "Document", "page", title="Secret Page")
        api.content.transition(obj=page, to_state="private")
        self.commit(wait=1)
        query = {"SearchableText": "secret"}
        self.assertEqual(
            len(self.es.secure_search(query)), 1, "A manager must find private content"
        )
        logout()
        self.assertEqual(
            len(self.es.secure_search(query)),
            0,
            "Anonymous must not find private content",
        )

    def test_anonymous_finds_expired_content_only_with_show_inactive(self):
        self.create_expired_page()
        logout()
        query = {"SearchableText": "expired"}
        self.assertEqual(
            len(self.es.secure_search(query)),
            0,
            "Anonymous must not find expired content",
        )
        self.assertEqual(
            len(self.es.secure_search({**query, "show_inactive": True})),
            1,
            "show_inactive=True must reveal expired content",
        )

    def test_show_inactive_false_hides_expired_content_from_managers(self):
        self.create_expired_page()
        query = {"SearchableText": "expired"}
        self.assertEqual(
            len(self.es.secure_search(query)),
            1,
            "A manager may see expired content by default",
        )
        self.assertEqual(
            len(self.es.secure_search({**query, "show_inactive": False})),
            0,
            "show_inactive=False must hide expired content, like the catalog does",
        )

    def test_finds_content_when_es_only_indexes_are_removed_from_catalog(self):
        api.content.create(self.portal, "Document", "page", title="A Fancy Title")
        self.commit(wait=1)
        for idx in getESOnlyIndexes():
            self.catalog._catalog.delIndex(idx)
        self.commit()
        results = self.es.secure_search({"SearchableText": "fancy"})
        self.assertEqual(
            [brain.getId for brain in results],
            ["page"],
            "SearchableText must be searched in elasticsearch",
        )
