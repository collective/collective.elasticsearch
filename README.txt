Introduction
============

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
