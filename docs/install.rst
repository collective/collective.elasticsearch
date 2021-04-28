Installation
============

collective.elasticsearch
------------------------

To install collective.elasticsearch into the global Python environment (or a workingenv),
using a traditional Zope 2 instance, you can do this:

* When you're reading this you have probably already run
  ``easy_install collective.elasticsearch``. Find out how to install setuptools
  (and EasyInstall) here:
  http://peak.telecommunity.com/DevCenter/EasyInstall

* If you are using Zope 2.9 (not 2.10), get `pythonproducts`_ and install it
  via::

    python setup.py install --home /path/to/instance

into your Zope instance.

* Create a file called ``collective.elasticsearch-configure.zcml`` in the
  ``/path/to/instance/etc/package-includes`` directory.  The file
  should only contain this::

    <include package="collective.elasticsearch" />

.. _pythonproducts: http://plone.org/products/pythonproducts


Alternatively, if you are using zc.buildout and the plone.recipe.zope2instance
recipe to manage your project, you can do this:

* Add ``collective.elasticsearch`` to the list of eggs to install, e.g.::

    [buildout]
    ...
    eggs =
        ...
        collective.elasticsearch

* Tell the plone.recipe.zope2instance recipe to install a ZCML slug::

    [instance]
    recipe = plone.recipe.zope2instance
    ...
    zcml =
        collective.elasticsearch

* Re-run buildout, e.g. with::

    $ ./bin/buildout

You can skip the ZCML slug if you are going to explicitly include the package
from another package's configure.zcml file.

elasticsearch
-------------

Less than 5 minutes:
    - Download & install Java
    - Download & install Elastic Search
    - bin/elasticsearch

Step by Step for Ubuntu:
    - add-apt-repository ppa:webupd8team/java
    - apt-get update
    - apt-get install git curl oracle-java7-installer
    - wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-7.6.0-linux-x86_64.tar.gz
    - wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-7.6.0-linux-x86_64.tar.gz.sha512
    - shasum -a 512 -c elasticsearch-7.6.0-linux-x86_64.tar.gz.sha512 
    - tar -xzf elasticsearch-7.6.0-linux-x86_64.tar.gz
    - cd elasticsearch
    - bin/elasticsearch

Step by Step for CentOS/RedHat:
    - yum -y install java-1.8.0-openjdk.x86_64
    - alternatives --auto java
    - curl -O https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-7.6.0.tar.gz
    - tar xfvz elasticsearch-7.6.0.tar.gz
    - cd elasticsearch
    - bin/elasticsearch

Does it work?
    - curl http://localhost:9200/
    - Do you see the Hudsucker Proxy reference? "You Know, for Search"
