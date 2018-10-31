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


Changing the index used for elasticsearch
-----------------------------------------

The index used for elasticsearch is the path to the portal_catalog by default. So you don't have anything to do if
you have several plone site on the same instance (the plone site id would be different).

However, if you want to use the same elasticsearch instance with several plone instance, you may
end up having conflicts. In that case, you may want to manually set the index used by adding the following code
to the ``__init__.py`` file of your module::

    from Products.CMFPlone.CatalogTool import CatalogTool
    from collective.elasticsearch.es import CUSTOM_INDEX_NAME_ATTR

    setattr(CatalogTool, CUSTOM_INDEX_NAME_ATTR, "my_elasticsearch_custom_index")


Adding custom index which are not in the catalog
------------------------------------------------

An adapter is used to define the mapping between the index and the elasticsearch properties. You can override
the _default_mapping attribute to add your own indexes::

    <adapter
        factory=".mapping.MyMappingAdapter"
        provides="collective.elasticsearch.interfaces.IMappingProvider"
        for="zope.interface.Interface
             collective.elasticsearch.interfaces.IElasticSearchCatalog"
        layer=".layers.MyLayer" />

::

    @implementer(IMappingProvider)
    class MyMappingAdapter(object):

        _default_mapping = {
            'SearchableText': {'store': False, 'type': 'text', 'index': True},
            'Title': {'store': False, 'type': 'text', 'index': True},
            'Description': {'store': False, 'type': 'text', 'index': True},
            'MyOwnIndex': {'store': False, 'type': 'text', 'index': True,
        }


Changing the settings of the index
----------------------------------

If you want to customize your elasticsearch index, you can override the ``get_index_creation_body`` method on the ``MappingAdapter``::

    @implementer(IMappingProvider)
    class MyMappingAdapter(object):

        def get_index_creation_body(self):
            return {
                "settings" : {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            }


Changing the query made to elasticsearch
----------------------------------------

The query generation is handled by another adapter::

    <adapter
        factory=".query.QueryAssembler"
        provides=".interfaces.IQueryAssembler"
        for="zope.interface.Interface
             .interfaces.IElasticSearchCatalog" />

You will have to override the ``__call__`` method to change the query. Look at the original adapter to have a better
idea on what you need to change.
