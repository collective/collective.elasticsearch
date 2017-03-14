Configuration
=============

Basic configuration
-------------------

- Goto Control Panel
- Add "Eleastic Search" in Add-on Products
- Click "Elastic Search" in "Add-on Configuration"
- Enable
- Click "Convert Catalog"
- Click "Rebuild Catalog"


Change the index used for elasticsearch
---------------------------------------

The index used for elasticsearch is the path to the portal_catalog by default. So you don't have anything to do if
you have several plone site on the same instance (the plone site id would be different).

However, if you want to use the same elasticsearch instance with several plone instance, you may
end up having conflicts. In that case, you may want to manually set the index used by adding the following code
to the ``__init__.py`` file of your module::

    from Products.CMFPlone.CatalogTool import CatalogTool
    from collective.elasticsearch.es import CUSTOM_INDEX_NAME_ATTR

    setattr(CatalogTool, CUSTOM_INDEX_NAME_ATTR, "my_elasticsearch_custom_index")

