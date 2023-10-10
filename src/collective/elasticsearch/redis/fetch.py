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


def fetch_data(uuid, attributes):
    backend = os.environ.get("PLONE_BACKEND", None)
    url = backend + "/@elasticsearch_extractdata"
    payload = {"uuid": uuid, "attributes:list": attributes}
    response = session.get(url, params=payload, verify=False, timeout=60)
    if response.status_code == 200:
        content = response.json()
        if "@id" in content and "data" in content:
            return content["data"]
    else:
        raise Exception(
            f"Bad response from Plone Backend: {response.status_code} \n {response.content}"
        )


def fetch_blob_data(fieldname, data):
    backend = os.environ.get("PLONE_BACKEND", None)
    download_url = "/".join([backend, data[fieldname]["path"], "@@download", fieldname])
    file_ = session_data.get(download_url)
    return io.BytesIO(file_.content)
