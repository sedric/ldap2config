#!/usr/bin/env python
# -*- coding: utf-8 -*-

# For Python3, install pyldap instead of ldap3 which break LDAP API
import ldap
import random
import subprocess
import os
import sys
import logging
import hashlib
import jinja2
from pwd import getpwnam
import grp

if sys.version_info < (2, 8):
  import ConfigParser
elif sys.version_info > (3, 0):
  import configparser as ConfigParser


def main():
  try:
    configfile = sys.argv[1]
    conffd = ConfigParser.ConfigParser()
    conffd.read(configfile)
  except IndexError:
    print("Usage: " + sys.argv[0] + " /path/to/config.ini")
    sys.exit(1)

  confcfg, ldapcfg, searchcfg, conflog = config_as_dicts(conffd)
  confcfg['template'] = import_template(confcfg['template']) # str => Jinja2Object

  logging.basicConfig(format='%(levelname)s: in %(funcName)s %(message)s',
                      level=conflog['level'])
  datas = get_datas_from_ldap(ldapcfg, searchcfg)
  logging.debug("LDAP extract : " + str(datas))
  write_in_config_file(datas, confcfg, searchcfg['attrs'])


# Return configuration as multiple dicts (hardcoded to raise config errors)
def config_as_dicts(config):
  ldapcfg   = {}
  searchcfg = {}
  confcfg   = {}
  conflog   = {}

  ldapcfg['user']      = config.get("ldap", "user")
  ldapcfg['pass']      = config.get("ldap", "pass")
  ldapcfg['host']      = config.get("ldap", "host")
  ldapcfg['port']      = config.get("ldap", "port")

  searchcfg['base'  ]  = config.get("search", "base")
  searchcfg['scope' ]  = eval(config.get("search", "scope"))
  searchcfg['filter']  = config.get("search", "filter")
  searchcfg['attrs' ]  = list(config.get("search", "attrs").split(' '))

  confcfg['cfgfile']   = config.get("config", "cfgfile")
  confcfg['owner'  ]   = config.get("config", "owner")
  confcfg['group'  ]   = config.get("config", "group")
  confcfg['mode'   ]   = config.get("config", "mode")
  # octal, octal, octal...
  if (sys.version_info < (2, 8)):
    confcfg['mode']    = "0" + confcfg['mode']
    confcfg['mode']    = eval(confcfg['mode'])
  elif (sys.version_info > (3, 0)):
    confcfg['mode']    = "0o" + confcfg['mode']
    confcfg['mode']    = eval(confcfg['mode'])
  confcfg['template' ] = config.get("config", "template")
  confcfg['on_change'] = config.get("config", "on_change")

  conflog['level']     = config.get("log", "level")

  return confcfg, ldapcfg, searchcfg, conflog


def items_as_dict(items):
  args = {}

  for item in items:
    key = item[0]
    args[key] = item[1]
  return args


# Take a file as argument and return it content as a Jinja2Obj
def import_template(template):
  loader = jinja2.FileSystemLoader(os.path.dirname(template))
  env = jinja2.Environment(loader=loader)
  tpl = env.get_template(os.path.basename(template))
  return tpl

# Remove DN, add missingg
def sanitize_ldap_datas(datas, attrs):
  i         = 0
  sanitized = []

  for data in datas:
    sanitized.append({})
    # A loop to add potentials attributes that are not in LDAP for a specific
    # object
    for attr in attrs:
      try:
        if (sys.version_info < (2, 8)):
          sanitized[i][attr] = data[1][attr]
        elif (sys.version_info > (3,0)):
          j = 0
          sanitized[i][attr] = []
          for value in data[1][attr]:
            sanitized[i][attr].append(value.decode())
      except (KeyError, IndexError):
#        pass
        sanitized[i][attr]    = ['']
    i = i + 1
  return sanitized


# Connect to LDAP and get datas as asked in the search section.
# Remove a layer in response to avoid getting the full DN (which is useless)
def get_datas_from_ldap(ldapcfg, searchcfg):
  server    = ldap.initialize('ldap://' + ldapcfg['host'])

  try:
    server.protocol_version = ldap.VERSION3
    if not (ldapcfg['user'] == '') and not (ldapcfg['pass'] == ''):
      server.simple_bind_s(ldapcfg['user'], ldapcfg['pass'])
  except:
    raise

  try:
    datas = server.search_s(searchcfg['base'],
                            searchcfg['scope'],
                            searchcfg['filter'],
                            searchcfg['attrs'])
    # Remove DN from results
    return sanitize_ldap_datas(datas, searchcfg['attrs'])
  except:
    raise


# Write datas in a temporary file then move it to cfgfile
# This avoid moving an half-empty credential file and losing users
def write_in_config_file(datas, confcfg, attrs):
  if (sys.version_info < (2, 8)):
    maxint = sys.maxint
  elif (sys.version_info > (3,0)):
    maxint = sys.maxsize
  randint  = str(random.randint(0, maxint))
  tempfile = '/tmp/ldapconfig.' + randint
  try:
    uid    = getpwnam(confcfg['owner']).pw_uid
  except KeyError:
    logging.error("No user '" + confcfg['owner'] + "' found")
    sys.exit(1)
  try:
    gid    = grp.getgrnam(confcfg['group']).gr_gid
  except KeyError:
    logging.error("No group '" + confcfg['group'] + "' found, use default one")
    gid    = -1

  # Check if tempfile does not already exist and try to remove it
  try:
    if (os.path.isfile(tempfile)):
      os.remove(tempfile)
  except:
    logging.error("Temporary file already exists and is not writable. This should not happen. Please rerun the script")
    sys.exit(2)
  confcfg['template'].render(items=datas)
  ## Write datas on tempfile and set permissions
  with open(tempfile, 'w') as output:
    os.fchmod(output.fileno(), confcfg['mode'])
    os.fchown(output.fileno(), uid, gid)
    output.write(confcfg['template'].render(items=datas))

  # Move tempfile to it permanent location
  #subprocess.call(['ls', "-l", tempfile])
  move_if_need(tempfile,  confcfg['cfgfile'], confcfg['on_change'])


def md5(fname):
  hash_md5 = hashlib.md5()
  with open(fname, "rb") as f:
    for chunk in iter(lambda: f.read(4096), b""):
      hash_md5.update(chunk)
  return hash_md5.hexdigest()


def move_if_need(source, destination, action):

  try:
    os.path.isfile(destination)
    logging.debug("Calculating MD5 hashes")
    md5source = md5(source)
    md5dest   = md5(destination)

    if ( md5source == md5dest ):
      logging.debug("MD5 match. Doing nothing")
      subprocess.call(['rm', source])
      return False
    else:
      logging.debug("MD5 mismatch, changing configuration")
  except IOError:
    logging.debug("File " + source + " does not exists yet, creating it !")

  subprocess.call(['mv', source, destination])
  logging.debug("Executing post-action : " + action)
  try:
    subprocess.call(action.split(' '))
  except OSError:
    logging.error("Cannot execute")
    sys.exit(2)


if __name__ == '__main__':
    main()
