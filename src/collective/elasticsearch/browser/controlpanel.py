from collective.elasticsearch import logger
from collective.elasticsearch.es import ElasticSearchCatalog
from collective.elasticsearch.interfaces import IElasticSettings
from elasticsearch.exceptions import ConnectionError as conerror
from elasticsearch.exceptions import NotFoundError
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from urllib3.exceptions import NewConnectionError
from z3c.form import form

import math


class ElasticControlPanelForm(RegistryEditForm):
    form.extends(RegistryEditForm)
    schema = IElasticSettings

    label = "Elastic Search Settings"

    control_panel_view = "@@elastic-controlpanel"


class ElasticControlPanelFormWrapper(ControlPanelFormWrapper):
    index = ViewPageTemplateFile("controlpanel_layout.pt")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.portal_catalog = getToolByName(self.context, "portal_catalog")
        self.es = ElasticSearchCatalog(self.portal_catalog)

    @property
    def connection_status(self):
        try:
            return self.es.connection.status()["ok"]
        except conerror:
            return False
        except (
            conerror,
            ConnectionError,
            NewConnectionError,
            ConnectionRefusedError,
            AttributeError,
        ):
            try:
                health_status = self.es.connection.cluster.health()["status"]
                return health_status in ("green", "yellow")
            except (
                conerror,
                ConnectionError,
                NewConnectionError,
                ConnectionRefusedError,
                AttributeError,
            ):
                return False

    @property
    def es_info(self):
        try:
            info = self.es.connection.info()
            try:
                stats = self.es.connection.indices.stats(index=self.es.real_index_name)[
                    "indices"
                ][self.es.real_index_name]["primaries"]
                size_in_mb = stats["store"]["size_in_bytes"] / 1024.0 / 1024.0
                return [
                    ("Cluster Name", info.get("name")),
                    ("Elastic Search Version", info["version"]["number"]),
                    ("Number of docs", stats["docs"]["count"]),
                    ("Deleted docs", stats["docs"]["deleted"]),
                    ("Size", str(int(math.ceil(size_in_mb))) + "MB"),
                    ("Query Count", stats["search"]["query_total"]),
                ]
            except KeyError:
                return [
                    ("Cluster Name", info.get("name")),
                    ("Elastic Search Version", info["version"]["number"]),
                ]
        except NotFoundError:
            logger.warning("Error getting stats", exc_info=True)
            return []

    @property
    def active(self):
        return self.es.get_setting("enabled")


ElasticControlPanelView = layout.wrap_form(
    ElasticControlPanelForm, ElasticControlPanelFormWrapper
)
