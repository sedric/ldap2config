#!/usr/bin/env python
# -*- coding: utf-8 -*-

# For Python3, install pyldap instead of ldap3 which break LDAP API
import ldap
import random
import subprocess
import os, sys
import logging
from pwd import getpwnam

if (sys.version_info < (2, 8)):
  import ConfigParser
elif (sys.version_info > (3,0)):
  import configparser as ConfigParser

def main():
  try:
    configfile = sys.argv[1]
    conffd = ConfigParser.ConfigParser()
    conffd.read(configfile)
  except IndexError:
    print("Usage: " + sys.argv[0] + " /path/to/config.ini")
    sys.exit(1)

  confcfg, ldapcfg, searchcfg, defvalues, conflog = config_as_dicts(conffd)
  confcfg['template'] = import_template(confcfg['template'])

  logging.basicConfig(format='%(levelname)s: in %(funcName)s %(message)s',
                      level=conflog['level'])
  datas = get_datas_from_ldap(ldapcfg, searchcfg, defvalues, confcfg["separator"])
  logging.debug("LDAP extract : " + str(datas))
  logging.debug("Attrs : " + str(defvalues.keys()))
  write_in_config_file(datas, confcfg, defvalues, set(searchcfg['attrs'] + defvalues.keys()))

# Return configuration as multiple dicts (hardcoded)
def config_as_dicts(config):
  ldapcfg   = {}
  searchcfg = {}
  confcfg   = {}
  conflog   = {}

  ldapcfg['user']      = config.get("ldap", "user")
  ldapcfg['pass']      = config.get("ldap", "pass")
  ldapcfg['host']      = config.get("ldap", "host")
  ldapcfg['port']      = config.get("ldap", "port")

  searchcfg['base']    = config.get("search", "base")
  searchcfg['scope']   = eval(config.get("search", "scope"))
  searchcfg['filter']  = config.get("search", "filter")
  searchcfg['attrs']   = list(config.get("search", "attrs").split(' '))

  confcfg['cfgfile']   = config.get("config", "cfgfile")
  confcfg['owner']     = config.get("config", "owner")
  confcfg['mode']      = config.get("config", "mode")
  # octal, octal, octal...
  if (sys.version_info < (2, 8)):
    confcfg['mode'] = "0" + confcfg['mode']
    confcfg['mode'] = eval(confcfg['mode'])
  elif (sys.version_info > (3,0)):
    confcfg['mode'] = "0o" + confcfg['mode']
    confcfg['mode'] = eval(confcfg['mode'])
  confcfg['template']  = config.get("config", "template")
  confcfg['separator'] = config.get("config", "tpl_separator")

  conflog['level']      = config.get("log", "level")

  try:
    defvalues = items_as_dict(config.items("default_values"))
  except AttributeError:
    defvalues = None

  return confcfg, ldapcfg, searchcfg, defvalues, conflog

def items_as_dict(items):
  args = {}

  for item in items:
    key = item[0]
    args[key] = item[1]
  return args

# Return an int corresponding to the largest number of values possible for an
# attribute list
# Used to define how many time a template can be rewriten for a given DN
def max_values_of_attributes(data, attrs):
  oldlen = 0
  for attr in attrs:
    try:
      thislen = len(data[attr])
    except TypeError:
      thislen = 0
    if (thislen > oldlen):
      maxlen = thislen


  return maxlen

# Take a file as argument and return it content as a string
def import_template(template):
  tpl = ""
  with open(template, 'r') as fd:
    tpl += fd.read()
  return tpl

# Connect to LDAP and get datas as asked in the search section.
# Remove a layer in response to avoid getting the full DN (which is useless)
def get_datas_from_ldap(ldapcfg, searchcfg, defvalues, separator):
  server    = ldap.initialize('ldap://' + ldapcfg['host'])
  sanitized = []
  i         = 0

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
    for data in datas:
      sanitized.append({})
      # A loop to add potentials attributes that are not in LDAP for a specific
      # object
      for attr in set(searchcfg['attrs'] + defvalues.keys()):
        try:
          if (sys.version_info < (2, 8)):
            sanitized[i][attr] = data[1][attr]
          elif (sys.version_info > (3,0)):
            j = 0
            sanitized[i][attr] = []
            for value in data[1][attr]:
              sanitized[i][attr].append(value.decode())
        except (KeyError, IndexError):
          sanitized[i][attr]    = ['']
          sanitized[i][attr][0] = get_attr_value_from_default(data, defvalues, attr, separator)
      i = i + 1
    return sanitized
  except:
    raise

# Write datas in a temporary file then move it to cfgfile
# This avoid moving an half-empty credential file and losing users
def write_in_config_file(datas, confcfg, defvalues, attrs):
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

  # Check if tempfile does not already exist and try to remove it
  try:
    if (os.path.isfile(tempfile)):
      os.remove(tempfile)
  except:
    logging.error("Temporary file already exists and is not writable. This should not happen. Please rerun the script")
    sys.exit(2)

  # Write datas on tempfile and set permissions
  with open(tempfile, 'w') as output:
    os.fchmod(output.fileno(), confcfg['mode'])
    os.fchown(output.fileno(), uid, -1)
    for data in datas:
      lines = gen_conf_from_template(data,
                                     confcfg['template'],
                                     confcfg['separator'],
                                     defvalues,
                                     attrs)
      output.write(lines)

  # Move tempfile to it permanent location
  subprocess.call(['ls', "-l", tempfile])
  subprocess.call(['mv', tempfile, confcfg['cfgfile']])

# Get a value from defaults for a given attribute
# Recursively check for links if value contain separator at the begining and the
# end of the string
def get_attr_value_from_default(data, defvalues, attr, separator):
  try:
    if ( attr.lower() in defvalues                     and
         defvalues[attr.lower()].startswith(separator) and
         defvalues[attr.lower()].endswith(separator)   ):
      logging.debug("+++ had to make a link")
      lnattr = defvalues[attr.lower()].strip(separator)
      logging.debug("+++ " + attr + " => " + lnattr)
      new = get_attr_value_from_default(data, defvalues, lnattr, separator)
    elif (attr.lower() in data[1]) and (data[1][attr.lower()] != None):
      logging.debug("+++ use value from a link (" + str(attr) + ") : " +
                    str(data[1][attr.lower()]))
      new = data[1][attr.lower()][0]
    else:
      logging.debug("+++ use default value : " +
                    str(attr) + "(" + str(defvalues[attr.lower()]) + ")")
      new = defvalues[attr.lower()]
  except KeyError:
    logging.debug("Something wrong happen")
    new = None

  logging.debug("value = " + str(new))
  return new

# FIXME: Change name
# Return correct value for a given attribute blanks in data structure will be
# filled according to this assumptions :
#   1. In case the object got 1 value, this value will be used for all iteration
#   2. In case the object got n values the difference will be filled with
#      default values of the object
def get_attr_value_for_tpl(data, attr, defvalues, separator, i):
  logging.debug("+++ Data : " + str(data))
  if (len(data[attr]) >= i):
    logging.debug("+++ everything is fine : " + str(data[attr][i]))
    new = data[attr][i]
  elif (len(data[attr]) == 1) and (data[attr][0] != None):
    logging.debug("+++ use first value : " + str(data[attr][0]))
    new = data[attr][0]
  return new

# FIXME: Change name of get_attr_value_for_tpl()
# Return a string containing 1 or more modified templates filled with LDAP datas
#
# If an LDAP object got N values, the template will be played N times.
# For other objects who have a lesser number of values (n), we have
# get_attr_value_for_tpl() that take care of it.
def gen_conf_from_template(data, template, separator, defvalues, attrs):
  maxval = max_values_of_attributes(data, attrs)
  tpl    = [template] * maxval
  config = ""
  i      = 0
  logging.debug("++ " + str(attrs))
  #logging.debug("++ Doing : " + str(data) + " with " + str(maxval) " iters")
  while i < maxval:
    for attr in attrs:
      old = separator + attr + separator
      logging.debug("++ " + str(data["cn"]) + "(" + attr + " => " + str(data[attr]) + ")")
      new = get_attr_value_for_tpl(data, attr, defvalues, separator, i)
      tpl[i] = tpl[i].replace(old, new)
    i = i + 1

  for string in tpl:
    config = config + string

  return config

if __name__ == '__main__':
    main()
