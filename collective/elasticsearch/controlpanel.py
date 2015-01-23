from collective.elasticsearch.es import ElasticSearchCatalog
from collective.elasticsearch.interfaces import DISABLE_MODE
from collective.elasticsearch.interfaces import IElasticSettings
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from z3c.form import form
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile


class ElasticControlPanelForm(RegistryEditForm):
    form.extends(RegistryEditForm)
    schema = IElasticSettings

    label = u'Elasic Search Settings'

    control_panel_view = '@@elastic-controlpanel'


class ElasticControlPanelFormWrapper(ControlPanelFormWrapper):
    index = ViewPageTemplateFile('controlpanel_layout.pt')

    def __init__(self, *args, **kwargs):
        super(ElasticControlPanelFormWrapper, self).__init__(*args, **kwargs)
        self.portal_catalog = getToolByName(self.context, 'portal_catalog')
        self.es = ElasticSearchCatalog(self.portal_catalog)

    @property
    def connection_status(self):
        try:
            return self.es.connection.status()['ok']
        except AttributeError:
            return self.es.connection.cluster.health()['status'] in ('green', 'yellow')
        except:
            return False

    @property
    def active(self):
        return self.es.registry.mode != DISABLE_MODE

ElasticControlPanelView = layout.wrap_form(ElasticControlPanelForm,
                                           ElasticControlPanelFormWrapper)
