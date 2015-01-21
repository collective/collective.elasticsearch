from zope.component.hooks import setSite
import transaction
import random
from collective.elasticsearch.testing import createObject
import os
from lxml.etree import iterparse
from lxml.html import fromstring, tostring
from DateTime import DateTime
from plone.app.textfield.value import RichTextValue
import requests


SITE_ID = 'Plone'


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
app = spoofRequest(app)  # noqa

_dir = os.path.join(os.getcwd(), 'src')


class DataReader(object):
    def __init__(self):
        self.data_file = open('wiki_data.xml')

    def __iter__(self):
        for event, elem in iterparse(self.data_file):
            if elem.tag == '{http://www.mediawiki.org/xml/export-0.8/}page':
                rev = elem.find(
                    '{http://www.mediawiki.org/xml/export-0.8/}revision')
                title = elem.find(
                    '{http://www.mediawiki.org/xml/export-0.8/}title').text
                resp = requests.get('http://en.wikipedia.org/wiki/' + title)
                html = fromstring(resp.content)
                yield {
                    'title': title,
                    'text': RichTextValue(
                        tostring(html.cssselect('#bodyContent')[0]),
                        mimeType='text/html',
                        outputMimeType='text/x-html-safe'),
                    'creation_date': DateTime(
                        rev.find(
                            '{http://www.mediawiki.org/xml/export-0.8/}timestamp').text),
                }


def importit(app):

    site = app[SITE_ID]
    setSite(site)
    per_folder = 50
    num_folders = 7
    max_depth = 4
    portal_types = ['Document', 'News Item', 'Event']
    data = iter(DataReader())

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
                try:
                    createObject(folder, random.choice(portal_types), 'page%i' % didx,
                                 check_for_first=True, delete_first=False,
                                 **data.next())
                    print 'created ', count
                except:
                    print 'error ', count
            count = populate(folder, count, depth + 1)
        print 'commiting'
        transaction.commit()
        app._p_jar.cacheMinimize()
        return count
    populate(site)

importit(app)
