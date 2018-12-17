# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup

import os


version = '2.0.4'

setup(
    name='collective.elasticsearch',
    version=version,
    description="elasticsearch integration with plone",
    long_description=(
        open('README.rst').read() +
        '\n' +
        open(os.path.join('docs', 'history.rst')).read()
    ),
    classifiers=[
        # Get more strings from
        # http://pypi.python.org/pypi?:action=list_classifiers
        'Framework :: Plone',
        'Programming Language :: Python',
        'Framework :: Plone',
        'Framework :: Plone :: 5.0',
        'Framework :: Plone :: 5.1',
    ],
    keywords='plone elasticsearch search indexing',
    author='Nathan Van Gheem',
    author_email='vangheem@gmail.com',
    url='http://svn.plone.org/svn/collective/',
    license='GPL',
    packages=find_packages(exclude=['ez_setup']),
    namespace_packages=['collective'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'setuptools',
        'elasticsearch>=2.0.0,<3.0.0',
        'plone.app.registry',
        'plone.api',
        'collective.monkeypatcher'
    ],
    extras_require={
        'test': [
            'plone.app.testing',
            'plone.testing',
            'unittest2',
            'plone.app.contenttypes',
            'collective.celery[test]'
        ],
        'test-wo-celery': [
            'plone.app.testing',
            'plone.testing',
            'unittest2',
            'plone.app.contenttypes',
        ],
        'test-archetypes': [
            'plone.app.testing',
            'plone.testing',
            'unittest2',
            'Products.ATContentTypes',
        ],
    },
    entry_points="""
    # -*- Entry points: -*-
    [celery_tasks]
    castle = collective.elasticsearch.hook

    [z3c.autoinclude.plugin]
    target = plone
    """,
)
