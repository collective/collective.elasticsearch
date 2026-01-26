from collective.elasticsearch.local import get_local

import io
import os
import requests


def _create_session():
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.auth = (
        str(os.environ.get("PLONE_USERNAME", None)),
        str(os.environ.get("PLONE_PASSWORD", None)),
    )
    return session


def _create_session_data():
    session = requests.Session()
    session.auth = (
        str(os.environ.get("PLONE_USERNAME", None)),
        str(os.environ.get("PLONE_PASSWORD", None)),
    )
    return session


def get_session():
    return get_local("fetch_session", _create_session)


def get_session_data():
    return get_local("fetch_session_data", _create_session_data)


def fetch_data(plone_url, uuid, attributes):
    if not plone_url:
        plone_url = os.environ.get("PLONE_BACKEND", None)
    url = plone_url + "/@elasticsearch_extractdata"
    payload = {"uuid": uuid, "attributes:list": attributes}
    response = get_session().get(url, params=payload, verify=False, timeout=60)
    if response.status_code == 200:
        content = response.json()
        if "@id" in content and "data" in content:
            return content["data"]
    else:
        raise Exception("Bad response from Plone Backend")


def fetch_blob_data(plone_url, fieldname, data):
    if not plone_url:
        plone_url = os.environ.get("PLONE_BACKEND", None)
    download_url = "/".join(
        [plone_url, data[fieldname]["path"], "@@download", fieldname]
    )
    file_ = get_session_data().get(download_url)
    return io.BytesIO(file_.content)
