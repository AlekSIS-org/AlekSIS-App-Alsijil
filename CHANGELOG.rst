Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog`_,
and this project adheres to `Semantic Versioning`_.

`2.0b0`_ - 2021-05-21
---------------------

Added
~~~~~
* Show a status icon for every lesson (running, data complete, data missing, etc.).
* Add buttons to go the the next/previous lesson (on the day/for the group).
* Add support for custom excuse types.
* Add group notes field.
* Add option to configure extra marks for personal notes.
* Add week select in week view.
* Carry over data between adjacent lessons if not already filled out.
* Student view with all personal notes and some statistics.
    * Mark personal notes as excused.
    * Reset personal notes.
    * Multiple selection/filter/sorting.
* Add overview of all groups a person is an owner of ("My groups").
* Implement intelligent permission rules.
* Add overview of all students with some statistics ("My students").
* Use django-reversion to keep an auditlog.
* Add page with affected lessons to register absence form.
* Check plausibility of class register data.
* Manage group roles (like class services).

Changed
~~~~~~~
* Redesign and optimise MaterializeCSS frontend.
    * Organise information in multiple tabs.
    * Show lesson topic, homework and group note in week view.
    * Improve mobile design.
* Improve error messages if there are no matching lesson periods.
* Filter personal notes in full register printout by school term.
* Allow teachers to open lessons on the same day before they actually start.
* Count and sum up tardiness.
* Do not allow entries in holidays (configurable).
* Support events and extra lessons as class register objects.

Fixed
~~~~~
* Show only group members in the week view.
* Make register absence form complete.
* Repair and finish support for substitutions.

`2.0a1`_ - 2020-02-01
---------------------

Changed
~~~~~~~

* Migrate to MaterializeCSS.
* Use one card per day in week view.

Removed
~~~~~~~
* Remove SchoolRelated and all related uses.


`1.0a3`_ - 2019-11-24
---------------------

Added
~~~~~

* Allow to register absences and excuses centrally.
* Statistical evaluation of text snippets in personal notes.
* Add overview per person to register printout.

Fixed
~~~~~

* Show lesson documentations in printout again.
* Allow pages overflowing in printout
* Show all relevant personal notes in week view.

`1.0a2`_ - 2019-11-11
--------

Added
~~~~~

* Display sum of absences and tardiness in printout.
* Auto-calculate absences for all following lessons when saving a lesson.

Changed
~~~~~~~

* Allow superusers to create lesson documentations in the future.

Fixed
~~~~~

* Fixed minor style issues in register printout.

`1.0a1`_ - 2019-09-17
--------

Added
~~~~~

* Display audit trail in lesson view.
* Add printout of register for archival purposes.

Fixed
~~~~~

* Fix off-by-one error in some date headers.
* Deduplicate lessons of child groups in group week view.
* Keep selected group in group week view when browsing weeks.
* Correctly display substitutions in group week view.
* Support underfull school weeks (at start and end of timetable effectiveness).
* Use bootstrap buttons everywhere.

.. _Keep a Changelog: https://keepachangelog.com/en/1.0.0/
.. _Semantic Versioning: https://semver.org/spec/v2.0.0.html

.. _1.0a1: https://edugit.org/AlekSIS/Official/AlekSIS-App-Alsijil/-/tags/1.0a1
.. _1.0a2: https://edugit.org/AlekSIS/Official/AlekSIS-App-Alsijil/-/tags/1.0a2
.. _1.0a3: https://edugit.org/AlekSIS/Official/AlekSIS-App-Alsijil/-/tags/1.0a3
.. _2.0a1: https://edugit.org/AlekSIS/Official/AlekSIS-App-Alsijil/-/tags/2.0a1
.. _2.0b0: https://edugit.org/AlekSIS/Official/AlekSIS-App-Alsijil/-/tags/2.0b0
