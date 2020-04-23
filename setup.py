# -*- coding: utf-8 -*-
"""Installer for the collective.elasticsearch package."""

from setuptools import find_packages
from setuptools import setup


long_description = '\n\n'.join([
    open('README.rst').read(),
    open('CONTRIBUTORS.rst').read(),
    open('CHANGES.rst').read(),
])


setup(
    name='collective.elasticsearch',
    version='3.0.5.dev0',
    description="elasticsearch integration with plone",
    long_description=long_description,
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        'Framework :: Plone :: 5.0',
        "Framework :: Plone :: 5.1",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords='plone elasticsearch search indexing',
    author='Nathan Van Gheem',
    author_email='vangheem@gmail.com',
    url='https://github.com/collective/collective.elasticsearch',
    project_urls={
        'PyPI': 'https://pypi.python.org/pypi/collective.elasticsearch',
        'Source': 'https://github.com/collective/collective.elasticsearch',
        'Tracker': 'https://github.com/collective/collective.elasticsearch/issues',
        # 'Documentation': 'https://collective.elasticsearch.readthedocs.io/en/latest/',
    },
    license='GPL version 2',
    packages=find_packages('src', exclude=['ez_setup']),
    namespace_packages=['collective'],
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    python_requires="==2.7",
    install_requires=[
        'setuptools',
        'elasticsearch>=6.0.0,<7.0.0',
        'plone.app.registry',
        'plone.api',
        'collective.monkeypatcher',
    ],
    extras_require={
        'test': [
            'docker',
            'plone.app.testing',
            # Plone KGS does not use this version, because it would break
            # Remove if your package shall be part of coredev.
            # plone_coredev tests as of 2016-04-01.
            'plone.testing>=5.0.0',
            'unittest2',
            'plone.app.contenttypes',
            'plone.app.contentrules'
        ],
        'test-archetypes': [
            'docker',
            'plone.app.testing',
            'plone.testing>=5.0.0',
            'unittest2',
            'Products.ATContentTypes',
            'plone.app.contentrules'
        ],
    },
    entry_points="""
    [celery_tasks]
    castle = collective.elasticsearch.hook    
    [z3c.autoinclude.plugin]
    target = plone
    [console_scripts]
    update_locale = collective.elasticsearch.locales.update:update_locale
    """,
)
