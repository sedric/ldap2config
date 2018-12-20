ldap2config
===========

The purpose of this script is to generate configuration file from LDAP entries.

It works using two more configuration files :

- The main configuration file: an ini form configuration containing
  informations about the LDAP server, the file which will be created, logging,
  etc. See ``example.ini``
- A template file: Your configuraiton template, in jinja2. See ``example.tpl``

On invocation, ``ldap2config`` create a temporary file, then check if there is a
difference between it and the destination before moving it. After that, a script
can be called (for reloading a service, for example).

``ldap2config`` is tested on python 2.7 and 3.5.

Configuration
=============
There is 4 sections :

- ``[ldap]``: which deal with the ldap server connexion
- ``[config]``: which handle information about the generated configuration file
- ``[log]``: to control the logging system
- ``[$search]``: which is one or more sections for controling LDAP search filters.
  The section name is also the variable name used in template

ldap
----
Contain the following properties :

- ``user``: LDAP user (can be empty)
- ``pass``: Password for given user (can be empty)
- ``host``: LDAP Host
- ``port``: LDAP port
- ``searches``: List of search sections

config
------

- ``template``: Full path to the template file used to generate ``cfgfile``
- ``cfgfile``: Full path to the output file
- ``owner``: ``cfgfile`` file owner
- ``group``: ``cfgfile`` file group owner
- ``mode``: ``cfgfile`` file rights (in numeric)
- ``on_change``: Action to do when generated file and destination are different.
  You can set ``/bin/true`` to do nothing

log
---

- ``level``: Log level, according to the python ``logging`` library

$search
-------
All search sections should contain the following :

- ``base``: LDAP base tree
- ``scope``: Search scope, as for LDAP can be (as in python ``ldap`` library) :

  - ``ldap.SCOPE_BASE``,
  - ``ldap.SCOPE_ONELEVEL``,
  - ``ldap.SCOPE_SUBORDINATE``,
  - ``ldap.SCOPE_SUBTREE``
- ``filter``: The filter string
- ``attrs``: List of attributes that should be returned

Invocation
==========

Create a configuration file then :

.. code-block:: shell-session

   $ ldap2config.py configuration.ini

``ldap2config`` is thinked to be used as a cron job.
That's why it use ``config.on_change`` instead of a return values that could
trigger useless mails.

Enhancements
============
I have few ideas of what can be done next :

- Redirect log output to file or syslog
- Hability to have a per search ldap configuration

Beware
======
For backward compatibility reasons, I don't use the standard python3 LDAP
library (``ldap3``), but ``pyldap``.
