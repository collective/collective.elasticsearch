from collective.elasticsearch import utils
from plone import api
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import setRoles
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.testing import zope
from Products.CMFPlone.CatalogTool import CatalogTool

import collective.elasticsearch
import os
import redis
import time

MAX_CONNECTION_RETRIES = 20
DISABLE_SEARCH_PATCHES = "PLONE_ELASTICSEARCH_DISABLE_SEARCH_PATCHES"
SEARCH_PATCHED_METHODS = ("searchResults", "__call__", "unrestrictedSearchResults")


class ElasticSearch(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        super().setUpZope(app, configurationContext)
        self.loadZCML(package=collective.elasticsearch)

    def setUpPloneSite(self, portal):
        super().setUpPloneSite(portal)
        # install into the Plone site
        applyProfile(portal, "collective.elasticsearch:default")
        setRoles(portal, TEST_USER_ID, ("Member", "Manager"))
        workflowTool = api.portal.get_tool("portal_workflow")
        workflowTool.setDefaultChain("plone_workflow")


ElasticSearch_FIXTURE = ElasticSearch()
ElasticSearch_INTEGRATION_TESTING = IntegrationTesting(
    bases=(ElasticSearch_FIXTURE,), name="ElasticSearch:Integration"
)
ElasticSearch_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(ElasticSearch_FIXTURE,), name="ElasticSearch:Functional"
)
ElasticSearch_API_TESTING = FunctionalTesting(
    bases=(ElasticSearch_FIXTURE, zope.WSGI_SERVER_FIXTURE),
    name="ElasticSearch:API",
)


class RedisElasticSearch(ElasticSearch):
    def setUpPloneSite(self, portal):
        super().setUpPloneSite(portal)

        # Setup environ for redis testing
        os.environ["PLONE_BACKEND"] = portal.absolute_url()
        os.environ["PLONE_USERNAME"] = SITE_OWNER_NAME
        os.environ["PLONE_PASSWORD"] = SITE_OWNER_PASSWORD
        os.environ["PLONE_REDIS_DSN"] = "redis://localhost:6379/0"

        # Make sure tasks are not handled async in tests
        # from collective.elasticsearch.redis.tasks import queue
        # queue._is_async = False

        utils.get_settings().use_redis = True
        self._wait_for_redis_service()

    def _wait_for_redis_service(self):
        from collective.elasticsearch.redis.tasks import redis_connection

        counter = 0
        while True:
            if counter == MAX_CONNECTION_RETRIES:
                raise Exception("Cannot connect to redis service")
            try:
                if redis_connection().ping():
                    break
            except redis.ConnectionError:
                time.sleep(1)
                counter += 1


ElasticSearch_REDIS_FIXTURE = RedisElasticSearch()
ElasticSearch_REDIS_TESTING = FunctionalTesting(
    bases=(zope.WSGI_SERVER_FIXTURE, ElasticSearch_REDIS_FIXTURE),
    name="ElasticSearch:Redis",
)


class ElasticSearchWithoutSearchPatches(ElasticSearch):
    """Load the package with PLONE_ELASTICSEARCH_DISABLE_SEARCH_PATCHES set.

    Monkey patches can not be unloaded, so search patches applied by another
    layer of the same test run are removed while this layer is set up and
    restored afterwards.
    """

    def setUpZope(self, app, configurationContext):
        self.env_value = os.environ.get(DISABLE_SEARCH_PATCHES)
        os.environ[DISABLE_SEARCH_PATCHES] = "1"
        self.search_patches = {}
        for name in SEARCH_PATCHED_METHODS:
            old_name = f"_old_{name}"
            if old_name in CatalogTool.__dict__:
                original = CatalogTool.__dict__[old_name]
                self.search_patches[name] = (CatalogTool.__dict__[name], original)
                delattr(CatalogTool, old_name)
                delattr(CatalogTool, name)
                # Methods inherited from CMFCore were not defined on CatalogTool
                if getattr(CatalogTool, name) is not original:
                    setattr(CatalogTool, name, original)
        super().setUpZope(app, configurationContext)

    def tearDownZope(self, app):
        super().tearDownZope(app)
        for name, (replacement, original) in self.search_patches.items():
            setattr(CatalogTool, f"_old_{name}", original)
            setattr(CatalogTool, name, replacement)
        if self.env_value is None:
            del os.environ[DISABLE_SEARCH_PATCHES]
        else:
            os.environ[DISABLE_SEARCH_PATCHES] = self.env_value


ElasticSearch_NO_SEARCH_PATCHES_FIXTURE = ElasticSearchWithoutSearchPatches()
ElasticSearch_NO_SEARCH_PATCHES_TESTING = FunctionalTesting(
    bases=(ElasticSearch_NO_SEARCH_PATCHES_FIXTURE,),
    name="ElasticSearch:NoSearchPatches",
)
