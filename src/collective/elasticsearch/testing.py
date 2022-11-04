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

import collective.elasticsearch
import os
import redis
import time


MAX_CONNECTION_RETRIES = 20


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
        os.environ["PLONE_BACKEND"] = utils.PLONE_BACKEND = portal.absolute_url()
        os.environ["PLONE_USERNAME"] = utils.PLONE_USERNAME = SITE_OWNER_NAME
        os.environ["PLONE_PASSWORD"] = utils.PLONE_PASSWORD = SITE_OWNER_PASSWORD
        os.environ[
            "PLONE_REDIS_DSN"
        ] = utils.PLONE_REDIS_DSN = "redis://localhost:6379/0"

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
                if redis_connection.ping():
                    break
            except redis.ConnectionError:
                time.sleep(1)
                counter += 1


ElasticSearch_REDIS_FIXTURE = RedisElasticSearch()
ElasticSearch_REDIS_TESTING = FunctionalTesting(
    bases=(zope.WSGI_SERVER_FIXTURE, ElasticSearch_REDIS_FIXTURE),
    name="ElasticSearch:Redis",
)
