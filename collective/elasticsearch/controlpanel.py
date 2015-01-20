from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName
from plone.z3cform import layout
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from z3c.form import form

from collective.elasticsearch.interfaces import IElasticSettings
from collective.elasticsearch.es import ElasticSearch
from collective.elasticsearch.interfaces import DISABLE_MODE


class ElasticControlPanelForm(RegistryEditForm):
    form.extends(RegistryEditForm)
    schema = IElasticSettings

    label = u'Elasic Search Settings'

    control_panel_view = "@@elastic-controlpanel"


class ElasticControlPanelFormWrapper(ControlPanelFormWrapper):
    index = ViewPageTemplateFile('controlpanel_layout.pt')

    def __init__(self, *args, **kwargs):
        super(ElasticControlPanelFormWrapper, self).__init__(*args, **kwargs)
        self.portal_catalog = getToolByName(self.context, 'portal_catalog')
        self.es = ElasticSearch(self.portal_catalog)

    @property
    def connection_status(self):
        try:
            return self.es.conn.status()['ok']
        except AttributeError:
            return self.es.conn.cluster.health()['status'] in ('green', 'yellow')
        except:
            return False

    @property
    def active(self):
        return self.es.registry.mode != DISABLE_MODE

ElasticControlPanelView = layout.wrap_form(ElasticControlPanelForm,
                                           ElasticControlPanelFormWrapper)
