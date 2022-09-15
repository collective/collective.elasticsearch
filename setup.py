"""Installer for the collective.elasticsearch package."""
from pathlib import Path
from setuptools import find_packages
from setuptools import setup


long_description = f"""
{Path("README.md").read_text()}\n
{Path("CHANGELOG.md").read_text()}\n
"""


setup(
    name="collective.elasticsearch",
    version="5.0.0a1",
    description="elasticsearch integration with plone",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Plone :: 5.2",
        "Framework :: Plone :: 6.0",
        "Framework :: Plone :: Addon",
        "Framework :: Plone",
        "Framework :: Zope :: 4",
        "Framework :: Zope :: 5",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="plone elasticsearch search indexing",
    author="Nathan Van Gheem",
    author_email="vangheem@gmail.com",
    url="https://github.com/collective/collective.elasticsearch",
    project_urls={
        "PyPI": "https://pypi.python.org/pypi/collective.elasticsearch",
        "Source": "https://github.com/collective/collective.elasticsearch",
        "Tracker": "https://github.com/collective/collective.elasticsearch/issues",
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
        "elasticsearch==7.7.0",
        "plone.app.registry",
        "plone.api",
        "setuptools",
    ],
    extras_require={
        "test": [
            "plone.app.contentrules",
            "plone.app.contenttypes",
            "plone.restapi[test]",
            "plone.app.testing[robot]>=7.0.0a3",
            "plone.app.robotframework[test]>=2.0.0a5",
            "parameterized",
        ],
    },
    entry_points="""
    [celery_tasks]
    castle = collective.elasticsearch.hook
    [z3c.autoinclude.plugin]
    target = plone
    """,
)
