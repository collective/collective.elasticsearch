from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper

from collective.elasticsearch.interfaces import IElasticSettings
from plone.z3cform import layout
from z3c.form import form


class ElasticControlPanelForm(RegistryEditForm):
    form.extends(RegistryEditForm)
    schema = IElasticSettings

ElasticControlPanelView = layout.wrap_form(ElasticControlPanelForm,
                                           ControlPanelFormWrapper)
