# -*- coding: utf-8 -*-
"""Installer for the collective.elasticsearch package."""

from setuptools import find_packages
from setuptools import setup


long_description = "\n\n".join(
    [
        open("README.rst").read(),
        open("CONTRIBUTORS.rst").read(),
        open("CHANGES.rst").read(),
    ]
)


setup(
    name="collective.elasticsearch",
    version="4.0.1.dev0",
    description="elasticsearch integration with plone",
    long_description=long_description,
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 5.2",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords="plone elasticsearch search indexing",
    author="Nathan Van Gheem",
    author_email="vangheem@gmail.com",
    url="https://github.com/collective/collective.elasticsearch",
    project_urls={
        "PyPI": "https://pypi.python.org/pypi/collective.elasticsearch",
        "Source": "https://github.com/collective/collective.elasticsearch",
        "Tracker": "https://github.com/collective/collective.elasticsearch/issues",
        # 'Documentation': 'https://collective.elasticsearch.readthedocs.io/en/latest/',
    },
    license="GPL version 2",
    packages=find_packages("src", exclude=["ez_setup"]),
    namespace_packages=["collective"],
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.7",
    install_requires=[
        "setuptools",
        "elasticsearch>=7.0.0,<=7.14",
        "plone.api",
        "plone.app.registry",
        "setuptools",
    ],
    extras_require={
        "test": [
            "plone.app.contentrules",
            "plone.app.contenttypes",
            "plone.app.testing",
            "plone.testing>=5.0.0",
            "Products.ATContentTypes",
            "unittest2",
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
