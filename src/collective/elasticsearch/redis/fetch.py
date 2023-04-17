import io
import os
import requests


session = requests.Session()
session.headers.update({"Accept": "application/json"})
session.auth = (
    str(os.environ.get("PLONE_USERNAME", None)),
    str(os.environ.get("PLONE_PASSWORD", None)),
)

session_data = requests.Session()
session_data.auth = (
    str(os.environ.get("PLONE_USERNAME", None)),
    str(os.environ.get("PLONE_PASSWORD", None)),
)


def fetch_data(plone_url, uuid, attributes):
    if not plone_url:
        plone_url = os.environ.get("PLONE_BACKEND", None)
    url = plone_url + "/@elasticsearch_extractdata"
    payload = {"uuid": uuid, "attributes:list": attributes}
    response = session.get(url, params=payload, verify=False, timeout=60)
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
    file_ = session_data.get(download_url)
    return io.BytesIO(file_.content)
