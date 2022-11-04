from collective.elasticsearch import utils

import os
import requests


session = requests.Session()
session.headers.update({"Accept": "application/json"})
session.auth = (
    str(os.environ.get("PLONE_USERNAME", None)),
    str(os.environ.get("PLONE_PASSWORD", None)),
)


def fetch_data(uuid, attributes):
    url = utils.PLONE_BACKEND + "/@elasticsearch_extractdata"
    payload = {"uuid": uuid, "attributes:list": attributes}
    response = session.get(url, params=payload, verify=False, timeout=60)
    if response.status_code == 200:
        content = response.json()
        if "@id" in content and "data" in content:
            return content["data"]
    else:
        raise Exception("Bad response from Plone Backend")
