from collective.elasticsearch.interfaces import IElasticSearchLayer
from collective.elasticsearch.interfaces import IElasticSettings
from plone.restapi.controlpanels import RegistryConfigletPanel
from zope.component import adapter
from zope.interface import Interface


@adapter(Interface, IElasticSearchLayer)
class ElasticSearchSettingsConfigletPanel(RegistryConfigletPanel):
    """Control Panel endpoint"""

    schema = IElasticSettings
    configlet_id = "elasticsearch"
    configlet_category_id = "Products"
    title = "Elastic Search Settings"
    group = ""
    schema_prefix = "collective.elasticsearch.interfaces.IElasticSettings"
