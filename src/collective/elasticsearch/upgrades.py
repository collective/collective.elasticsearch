from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from zope.component import getUtility


def update_registry(context):
    portal_setup = getToolByName(context, "portal_setup")
    portal_setup.runImportStepFromProfile(
        "profile-collective.elasticsearch:default",
        "plone.app.registry",
        run_dependencies=False,
    )


def remove_raise_search_exception_record(context):
    registry = getUtility(IRegistry)
    record_name = (
        "collective.elasticsearch.interfaces.IElasticSettings.raise_search_exception"
    )
    if record_name in registry.records:
        del registry.records[record_name]
