from zope.app.component.hooks import setSite
import transaction
from datetime import datetime, timedelta
import random
from plone.i18n.normalizer import idnormalizer
from StringIO import StringIO
from collective.elasticsearch.convert import convert_to_elastic
from collective.elasticsearch.testing import createObject
import os

SITE_ID = 'Plone'
NUM_GALLERIES = 20
START_DATE = datetime(2012, 1, 1)
MAX_GALLERY_SIZE = 100


from Testing.makerequest import makerequest
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManager import setSecurityPolicy
from Products.CMFCore.tests.base.security import PermissiveSecurityPolicy, \
    OmnipotentUser


def spoofRequest(app):
    """
    Make REQUEST variable to be available on the Zope application server.

    This allows acquisition to work properly
    """
    _policy = PermissiveSecurityPolicy()
    setSecurityPolicy(_policy)
    newSecurityManager(None, OmnipotentUser().__of__(app.acl_users))
    return makerequest(app)

# Enable Faux HTTP request object
app = spoofRequest(app)

_dir = os.path.join(os.getcwd(), 'src', 'collective.elasticsearch')

class Data(object):
    def __init__(self):
        self.data_file = open(os.path.join(_dir, 'shortabstract_en.nt'))
    def next(self):
        try:
            return unicode(self.data_file.next().strip(
                '"@en .').split('#comment> "')[1], 'latin1')
        except:
            print 'can not find data..'
            return self.next()


def importit(app):

    site = app[SITE_ID]
    setSite(site)
    convert_to_elastic(site.portal_catalog)
    per_folder = 500
    num_folders = 50
    max_depth = 5
    portal_types = ['Document', 'News Item', 'Event']
    data = Data()

    def populate(parent, count=0, depth=0):
        if depth >= max_depth:
            return count
        for fidx in range(num_folders):
            count += 1
            folder = createObject(parent, 'Folder', 'folder%i' % fidx,
                                  check_for_first=True, delete_first=False,
                                  title="Folder %i" % fidx)
            for didx in range(per_folder):
                count += 1
                print 'created ', count
                createObject(folder, random.choice(portal_types), 'page%i' % didx,
                             check_for_first=True, delete_first=False,
                             title="Page %i" % didx, text=data.next())
            count = populate(folder, count, depth + 1)
        transaction.commit()
        app._p_jar.cacheMinimize()
        return count
    populate(site)

importit(app)
