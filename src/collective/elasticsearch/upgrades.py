from collective.elasticsearch.manager import ElasticSearchManager
from Products.CMFCore.utils import getToolByName


def update_registry(context):
    portal_setup = getToolByName(context, "portal_setup")
    portal_setup.runImportStepFromProfile(
        "profile-collective.elasticsearch:default",
        "plone.app.registry",
        run_dependencies=False,
    )


def update_attachment_pipeline(context):
    manager = ElasticSearchManager()
    if manager.active:
        manager._setup_attachment_pipeline_and_default_index()
