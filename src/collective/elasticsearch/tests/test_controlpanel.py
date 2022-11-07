from collective.elasticsearch.browser.controlpanel import ElasticControlPanelView
from collective.elasticsearch.tests import BaseRedisTest
from unittest import mock

import os


ENV_FOR_REDIS = {
    "PLONE_REDIS_DSN": "",
    "PLONE_BACKEND": "",
    "PLONE_USERNAME": "",
    "PLONE_PASSWORD": "",
}


class TestControlPanel(BaseRedisTest):
    def test_use_redis_checkbox_is_disabled_enabled(self):
        controlpanel = ElasticControlPanelView(self.portal, self.request)
        controlpanel.update()

        self.assertIsNone(controlpanel.form_instance.widgets["use_redis"].disabled)

        with mock.patch.dict(os.environ, ENV_FOR_REDIS):
            controlpanel.update()
            self.assertEqual(
                "disabled", controlpanel.form_instance.widgets["use_redis"].disabled
            )
