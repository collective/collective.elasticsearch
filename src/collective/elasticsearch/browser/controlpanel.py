from collective.elasticsearch.interfaces import IElasticSettings
from collective.elasticsearch.manager import ElasticSearchManager
from elasticsearch.exceptions import ConnectionError as conerror
from plone import api
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from urllib3.exceptions import NewConnectionError
from z3c.form import form


class ElasticControlPanelForm(RegistryEditForm):
    form.extends(RegistryEditForm)
    schema = IElasticSettings

    label = "Elastic Search Settings"

    control_panel_view = "@@elastic-controlpanel"


class ElasticControlPanelFormWrapper(ControlPanelFormWrapper):
    index = ViewPageTemplateFile("controlpanel_layout.pt")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.portal_catalog = api.portal.get_tool("portal_catalog")
        self.es = ElasticSearchManager()

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
        return self.es.info

    @property
    def enabled(self):
        return self.es.enabled

    @property
    def active(self):
        return self.es.active


ElasticControlPanelView = layout.wrap_form(
    ElasticControlPanelForm, ElasticControlPanelFormWrapper
)
