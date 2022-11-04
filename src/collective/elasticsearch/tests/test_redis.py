from collective.elasticsearch import utils
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.tests import BaseRedisTest

import os
import unittest


ENV_FOR_REDIS = {
    "PLONE_REDIS_DSN": "redis://localhost:6379/0",
    "PLONE_BACKEND": "http://localhost",
    "PLONE_USERNAME": "admin",
    "PLONE_PASSWORD": "password",
}


class TestRedisUtils(BaseFunctionalTest):
    def test_redis_not_available_if_environ_vars_are_missing(self):

        self.assertFalse(
            utils.is_redis_available(), "Env vars are missing, this should be false"
        )

        with unittest.mock.patch.dict(os.environ, ENV_FOR_REDIS):
            self.assertTrue(
                utils.is_redis_available(),
                "All env vars ar available, this should be true",
            )


class TestUseRedis(BaseRedisTest):
    def test_use_redis_if_configured(self):
        utils.get_settings().use_redis = False
        self.assertFalse(utils.use_redis(), "Using redis should be disabled")

        utils.get_settings().use_redis = True
        self.assertTrue(utils.use_redis(), "Using redis should be enabled")
