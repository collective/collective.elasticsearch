Introduction
============

Install elasticsearch
---------------------

Less than 5 minutes:
    - Download & install Java
    - Download & install Elastic Search
    - bin/elasticsearch -f

Step by Step for Ubuntu:
    - add-apt-repository ppa:webupd8team/java
    - apt-get update
    - apt-get install git curl oracle-java7-installer
    - curl -O https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-0.90.1.tar.gz
    - tar xfvz elasticsearch-0.90.1.tar.gz
    - cd elasticsearch
    - bin/elasticsearch -f &

Does it work?
    - telnet http://localhost:9200/
    - Do you see the Hudsucker Proxy reference? "You Know, for Search"

Use Elastic Search in Plone:
    - Add collective.elasticsearch to eggs & re-run buildout
    - Restart Plone
    - Goto Control Panel
    - Add "Eleastic Search" in Add-on Products
    - Click "Elastic Search" in "Add-on Configuration"
    - Pick a mode
    - Click "Convert Catalog"
    - Click "Rebuild Catalog"

You now have a insanely scalable modern search engine. Now live the life of the Mind!

Overview
--------

This package aims to be a drop in replacement the portal_catalog
with elasticsearch.

There are 3 modes:
    - disabled: will not use elasticsearch
    - replacement: completely replaces, old catalog no longer used
    - dual: still index objects in portal_catalog, just use
      elasticsearch for searching


Options
-------

connection string
    elasticsearch connection string
mode
    What mode to put elasticsearch into(default disabled)
auto flush
    if after every index, flush should be performed.
    If on, things are always updated at a cost of performance.

TODO
----

- optimize?

- get it to work with SaAS provider, e.g. searchbox.io so people dont have to install eleasticsearch locally to evaluate
