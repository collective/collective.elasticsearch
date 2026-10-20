from collective.elasticsearch.tests import BaseFunctionalTest
from plone import api
from plone.registry import field
from plone.registry import Record
from plone.registry.interfaces import IRegistry
from zope.component import getUtility

RAISE_SEARCH_EXCEPTION_RECORD = (
    "collective.elasticsearch.interfaces.IElasticSettings.raise_search_exception"
)


class TestUpgradeToVersionFive(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        self.registry = getUtility(IRegistry)
        self.setup = api.portal.get_tool("portal_setup")
        self.setup.setLastVersionForProfile("collective.elasticsearch:default", "4")

    def upgrade(self):
        self.setup.upgradeProfile("collective.elasticsearch:default")

    def test_removes_the_raise_search_exception_record(self):
        self.registry.records[RAISE_SEARCH_EXCEPTION_RECORD] = Record(
            field.Bool(title="Raise Search Exceptions"), False
        )
        self.upgrade()
        self.assertNotIn(
            RAISE_SEARCH_EXCEPTION_RECORD,
            self.registry.records,
            "The upgrade must remove the stale registry record",
        )

    def test_runs_without_the_raise_search_exception_record(self):
        self.assertNotIn(
            RAISE_SEARCH_EXCEPTION_RECORD,
            self.registry.records,
            "Precondition: a fresh site has no raise_search_exception record",
        )
        self.upgrade()
        self.assertEqual(
            self.setup.getLastVersionForProfile("collective.elasticsearch:default"),
            ("5",),
            "The upgrade must run cleanly without the record",
        )
