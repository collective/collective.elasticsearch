from Products.CMFCore.utils import getToolByName
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from plone.app.testing import applyProfile
from plone.app.testing import setRoles
from plone.testing import z2
from zope.configuration import xmlconfig


class ElasticSearch(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        super(ElasticSearch, self).setUpZope(app, configurationContext)
        # load ZCML
        import plone.app.contenttypes
        xmlconfig.file('configure.zcml', plone.app.contenttypes,
                       context=configurationContext)
        z2.installProduct(app, 'plone.app.contenttypes')

        import plone.app.event.dx
        self.loadZCML(package=plone.app.event.dx,
                      context=configurationContext)

        import plone.app.registry
        xmlconfig.file('configure.zcml', plone.app.registry,
                       context=configurationContext)
        z2.installProduct(app, 'plone.app.registry')

        import collective.elasticsearch
        xmlconfig.file('configure.zcml', collective.elasticsearch,
                       context=configurationContext)
        z2.installProduct(app, 'collective.elasticsearch')

    def setUpPloneSite(self, portal):
        super(ElasticSearch, self).setUpPloneSite(portal)
        # install into the Plone site
        applyProfile(portal, 'plone.app.registry:default')
        applyProfile(portal, 'plone.app.contenttypes:default')
        applyProfile(portal, 'collective.elasticsearch:default')
        setRoles(portal, TEST_USER_ID, ('Member', 'Manager'))
        workflowTool = getToolByName(portal, 'portal_workflow')
        workflowTool.setDefaultChain('plone_workflow')

    def tearDownPloneSite(self, portal):
        super(ElasticSearch, self).tearDownPloneSite(portal)
        applyProfile(portal, 'plone.app.contenttypes:uninstall')


ElasticSearch_FIXTURE = ElasticSearch()
ElasticSearch_INTEGRATION_TESTING = IntegrationTesting(
    bases=(ElasticSearch_FIXTURE,), name='ElasticSearch:Integration')
ElasticSearch_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(ElasticSearch_FIXTURE,), name='ElasticSearch:Functional')


def browserLogin(portal, browser, username=None, password=None):
    handleErrors = browser.handleErrors
    try:
        browser.handleErrors = False
        browser.open(portal.absolute_url() + '/login_form')
        if username is None:
            username = TEST_USER_NAME
        if password is None:
            password = TEST_USER_PASSWORD
        browser.getControl(name='__ac_name').value = username
        browser.getControl(name='__ac_password').value = password
        browser.getControl(name='submit').click()
    finally:
        browser.handleErrors = handleErrors


def createObject(context, _type, id, delete_first=True,
                 check_for_first=False, **kwargs):
    if delete_first and id in context:
        context.manage_delObjects([id])
    if not check_for_first or id not in context:
        return context[context.invokeFactory(_type, id, **kwargs)]

    return context[id]
