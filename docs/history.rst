Changelog
=========

2.0.6 (unreleased)
------------------

- Nothing changed yet.


2.0.5 (2018-12-20)
------------------

- Fix sort order parsing and implementation
  [vangheem]


2.0.4 (2018-12-17)
------------------

- Fix date queries to work with `min:max` as well as `minmax`
  [vangheem]


2.0.3 (2018-12-04)
------------------

- Add IReindexActive to request as a flag for other code
  [lucid-0]


2.0.2 (2018-11-27)
------------------

- Fix error upgrading collective.elasticsearch
  [vangheem]

- Fix error causing "Server Status" on @@elastic-controlpanel to be empty.
  [fulv]


2.0.1 (2018-01-05)
------------------

- Prevent critical error when by chance query value is None.
  [thomasdesvenain]

- Minor code cleanup: readability, pep8, 80 cols, zca decorators.
  [jensens]

- Fix date criteria: 'minmax' instead of 'min:max' + string to date conversion
  [ebrehault]


2.0.0a6 (2017-03-29)
--------------------

- Gracefully handle upgrades in the settings interface so it doesn't break
  for people upgrading.
  [vangheem]


2.0.0a5 (2017-03-29)
--------------------

- Running indexing as admin as it is possible to initiate reindex or index on an
  object that you do not have permissions for
  [vangheem]


2.0.0a4 (2017-03-27)
--------------------

- released


2.0.0a3 (2017-03-27)
--------------------

- Add a method to set the body of the request during index creation.
  [Gagaro]

- Fixed get brain in lazy list with negative indexes.
  [thomasdesvenain]

- The list of indexes that forces es search is configurable.
  [thomasdesvenain]

- Works under Plone 4.3.
  [thomasdesvenain]

- Works with archetypes contents.
  [thomasdesvenain]

2.0.0a2 (2016-07-19)
--------------------

- We can pass a custom results factory and custom query parameters
  to IElasticSearchCatalog.search() method.
  So we can use it as a public interface for custom needs.
  [thomasdesvenain]

- Prevent from unindex before reindex when uid is unchanged, for instance at rename.
  Use a set for to-remove list.
  [thomasdesvenain]

- Fix indexing when removing the Title and Description indexes from Plone
  [vangheem]

2.0.0a1 (2016-06-06)
--------------------

- upgrade to elasticsearch 2.x
  [vangheem]

1.0.1a4 (2016-05-22)
--------------------

- provide better search query
  [vangheem]

1.0.1a3 (2016-03-22)
--------------------

- make sure to get alias definition right
  [vangheem]

1.0.1a2 (2016-03-18)
--------------------

- create index as an alias so you can potentially work on an existing alias without needing
  downtime
  [vangheem]

1.0.1a1 (2016-02-25)
--------------------

- change default sorting to descending.
  Closes: https://github.com/collective/collective.elasticsearch/issues/12
  [neilferreira]

1.0.0a1 (2016-02-25)
--------------------

- Initial release
