# -*- coding: utf-8 -*-
from Products.CMFCore.utils import getToolByName


def update_registry(context):
    portal_setup = getToolByName(context, 'portal_setup')
    portal_setup.runImportStepFromProfile(
        'profile-collective.elasticsearch:default',
        'plone.app.registry',
        run_dependencies=False,
    )
