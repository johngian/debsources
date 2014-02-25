# Copyright (C) 2013-2014  Stefano Zacchiroli <zack@upsilon.cc>
#
# This file is part of Debsources.
#
# Debsources is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import ConfigParser as configparser
import importlib
import logging
import os
import sys
import updater


DEFAULT_CONFIG = {
    'dry_run':     'false',
    'passes':      'db fs hooks hooks.db hooks.fs',
    'log_level':   'info',
    'expire_days': '0',
    'force_triggers': [],
    'single_transaction': 'true',
}

LOG_FMT_FILE = '%(asctime)s %(module)s:%(levelname)s %(message)s'
LOG_FMT_STDERR = '%(module)s:%(levelname)s %(message)s'
LOG_DATE_FMT = '%Y-%m-%d %H:%M:%S'

LOG_LEVELS = {	# XXX module logging has no built-in way to do this conversion
                # unless one uses the logging.config cannon. Really?!?
    'debug':    logging.DEBUG,		# verbosity >= 3
    'info':     logging.INFO,		# verbosity >= 2
    'warning':  logging.WARNING,	# verbosity >= 1
    'error':    logging.ERROR,		# verbosity >= 0
    'critical': logging.CRITICAL,
}


def load_configuration(conffile):
    """load configuration from file and return it as a (typed) dictionary
    """
    conf = configparser.SafeConfigParser(DEFAULT_CONFIG)
    conf.read(conffile)

    typed_conf = { 'conffile': conffile }
    for (key, value) in conf.items('infra'):
        if key == 'expire_days':
            value = int(value)
        elif key == 'dry_run':
            assert value in ['true', 'false']
            value = (value == 'true')
        elif key == 'hooks':
            value = value.split()
        elif key == 'log_level':
            value = LOG_LEVELS[value]
        elif key == 'passes':
            value = set(value.split())
        elif key == 'single_transaction':
            assert value in ['true', 'false']
            value = (value == 'true')
        typed_conf[key] = value
    return typed_conf


def load_hooks(conf):
    """load and initialize hooks from the corresponding Python modules

    return a pair (observers, extensions), where observers is a dictionary
    mapping events to list of subscribed callable, and extensions is a
    dictionary mapping per-package file extensions (to be found in the
    filesystem storage) to the owner plugin
    """
    observers = updater.NO_OBSERVERS
    file_exts = {}

    def subscribe_callback(event, action, title=""):
        if not event in updater.KNOWN_EVENTS:
            raise ValueError('unknown event type "%s"' % event)
        observers[event].append((title, action))

    def declare_ext_callback(ext, title=""):
        assert ext.startswith('.')
        assert not file_exts.has_key(ext)
        file_exts[ext] = title

    debsources = { 'subscribe': subscribe_callback,
                   'declare_ext': declare_ext_callback,
                   'config':    conf }
    for hook in conf['hooks']:
        plugin = importlib.import_module('plugins.hook_' + hook)
        plugin.init_plugin(debsources)

    return (observers, file_exts)


def log_level_of_verbosity(n):
    if n >= 3:
        return logging.DEBUG
    elif n >= 2:
        return logging.INFO
    elif n >= 1:
        return logging.WARNING
    else:
        return logging.ERROR


def init_logging(conf, console_verbosity=logging.ERROR):
    """initialize logging

    log everythong to logfile, log errors to stderr. stderr will be shown on
    console for interactive use, or mailed by cron.

    to completely disable logging to file ensure that the 'log_file' key is not
    defined in conf
    """
    logger = logging.getLogger()

    if conf.has_key('log_file'): # log to file and stderr, w/ different settings
        logging.basicConfig(level=logging.DEBUG,	# log everything by default
                            format=LOG_FMT_FILE,
                            datefmt=LOG_DATE_FMT,
                            filename=conf['log_file'])
        logger.handlers[0].setLevel(conf['log_level'])	# logfile verbosity

        stderr_log = logging.StreamHandler()
        stderr_log.setLevel(console_verbosity)	# console verbosity
        stderr_log.setFormatter(logging.Formatter(LOG_FMT_STDERR))
        logger.addHandler(stderr_log)
    else:	# only log to stderr
        logging.basicConfig(level=console_verbosity,
                            format=LOG_FMT_STDERR,
                            datefmt=LOG_DATE_FMT)