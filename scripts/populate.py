from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManager import setSecurityPolicy
from lxml.html import fromstring
from lxml.html import tostring
from multiprocessing.pool import ThreadPool as Pool
from plone import api
from plone.app.textfield.value import RichTextValue
from Products.CMFCore.tests.base.security import OmnipotentUser
from Products.CMFCore.tests.base.security import PermissiveSecurityPolicy
from Testing.makerequest import makerequest
from unidecode import unidecode
from zope.component.hooks import setSite

import os
import random
import requests
import transaction


SITE_ID = "Plone"


def parse_url(url):
    resp = requests.get(url)
    return resp.content


def spoofRequest(app):  # NOQA W0621
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

_dir = os.path.join(os.getcwd(), "src")

_links = []  # type: list
_toparse = []  # type: list


def parse_urls(urls):
    with Pool(8) as pool:
        return pool.map(parse_url, urls)


class DataReader:
    base_url = "https://en.wikipedia.org"
    base_content_url = base_url + "/wiki/"
    start_page = base_content_url + "Main_Page"
    title_selector = "#firstHeading"
    content_selector = "#bodyContent"

    def __init__(self):
        self.parsed = []
        self.toparse = [self.start_page]
        self.toprocess = []

    def get_content(self, html, selector, text=False):  # NOQA R0201
        els = html.cssselect(selector)
        if len(els) > 0:
            if text:
                return unidecode(els[0].text_content())
            return tostring(els[0])
        return None

    def __iter__(self):
        while len(self.toparse) > 0:
            if len(self.toprocess) == 0:
                toparse = [
                    self.toparse.pop(0) for _ in range(min(20, len(self.toparse)))
                ]
                self.toprocess = parse_urls(toparse)
                self.parsed.extend(toparse)
            html = fromstring(self.toprocess.pop(0))

            # get more links!
            for el in html.cssselect("a"):
                url = el.attrib.get("href", "")
                if url.startswith("/"):
                    url = self.base_url + url
                if url.startswith(self.base_content_url) and url not in self.parsed:
                    self.toparse.append(url)

            title = self.get_content(html, self.title_selector, text=True)
            body = self.get_content(html, self.content_selector)
            if not title or not body:
                continue

            yield {
                "title": f"{title}",
                "text": RichTextValue(
                    body.decode("utf-8"),
                    mimeType="text/html",
                    outputMimeType="text/x-html-safe",
                ),
            }


def importit(app):  # NOQA W0621
    site = app[SITE_ID]
    setSite(site)
    per_folder = 50
    num_folders = 6
    max_depth = 4
    portal_types = ["Document", "News Item", "Event"]
    data = iter(DataReader())

    def populate(parent, count=0, depth=0):
        if depth >= max_depth:
            return count
        for fidx in range(num_folders):
            count += 1
            fid = f"folder{fidx}"
            if fid in parent.objectIds():
                folder = parent[fid]
            else:
                folder = api.content.create(
                    type="Folder",
                    title=f"Folder {fidx}",
                    id=fid,
                    exclude_from_nav=True,
                    container=parent,
                )
            for didx in range(per_folder):
                count += 1
                pid = f"page{didx}"
                if pid not in folder.objectIds():
                    payload = next(data)
                    try:
                        api.content.create(
                            type=random.choice(portal_types),
                            id=pid,
                            container=folder,
                            exclude_from_nav=True,
                            **payload,
                        )
                        print("created ", count)
                    except Exception:  # NOQA W0703
                        print("skipping", count)
            print("commiting")
            transaction.commit()
            count = populate(folder, count, depth + 1)
            app._p_jar.cacheMinimize()
        return count

    populate(site)


importit(app)
