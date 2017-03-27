from setuptools import setup, find_packages
import os

version = '2.0.0a4.dev0'

setup(name='collective.elasticsearch',
      version=version,
      description="elasticsearch integration with plone",
      long_description=open("README.rst").read() + "\n" +
                       open(os.path.join("docs", "history.rst")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "Framework :: Plone",
        "Programming Language :: Python",
        "Framework :: Plone",
        "Framework :: Plone :: 5.0",
        "Framework :: Plone :: 4.3"
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
