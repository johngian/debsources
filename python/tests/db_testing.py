# Copyright (C) 2013-2014  Stefano Zacchiroli <zack@upsilon.cc>
#                    2014  Matthieu Caneill <matthieu.caneill@gmail.com>
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

import os
import sqlalchemy
import subprocess

from os.path import abspath, dirname

import models

from subprocess_workaround import subprocess_setup
from testdata import *


TEST_DB_DUMP = os.path.join(TEST_DATA_DIR, 'db/pg-dump-custom')

# queries to compare two DB schemas (e.g. "public.*" and "ref.*")
DB_COMPARE_QUERIES = {
    "packages":
    "SELECT name \
     FROM %(schema)s.packages \
     ORDER BY name \
     LIMIT 100",

    "versions":
    "SELECT packages.name, vnumber, area, vcs_type, vcs_url, vcs_browser \
     FROM %(schema)s.versions, %(schema)s.packages \
     WHERE versions.package_id = packages.id \
     ORDER BY packages.name, vnumber \
     LIMIT 100",

    "suitesmapping":
    "SELECT packages.name, versions.vnumber, suite \
     FROM %(schema)s.versions, %(schema)s.packages, %(schema)s.suitesmapping \
     WHERE versions.package_id = packages.id \
     AND suitesmapping.sourceversion_id = versions.id \
     ORDER BY packages.name, versions.vnumber, suite \
     LIMIT 100",

    "files":
    "SELECT packages.name, versions.vnumber, files.path \
     FROM %(schema)s.files, %(schema)s.versions, %(schema)s.packages \
     WHERE versions.package_id = packages.id \
     AND files.version_id = versions.id \
     ORDER BY packages.name, versions.vnumber, files.path \
     LIMIT 100",

    "checksums":
    "SELECT packages.name, versions.vnumber, files.path, sha256 \
     FROM %(schema)s.files, %(schema)s.versions, %(schema)s.packages, %(schema)s.checksums \
     WHERE versions.package_id = packages.id \
     AND checksums.version_id = versions.id \
     AND checksums.file_id = files.id \
     ORDER BY packages.name, versions.vnumber, files.path \
     LIMIT 100",

    "sloccounts":
    "SELECT packages.name, versions.vnumber, language, count \
     FROM %(schema)s.sloccounts, %(schema)s.versions, %(schema)s.packages \
     WHERE versions.package_id = packages.id \
     AND sloccounts.sourceversion_id = versions.id \
     ORDER BY packages.name, versions.vnumber, language \
     LIMIT 100",

    "ctags":
    "SELECT packages.name, versions.vnumber, files.path, tag, line, kind, language \
     FROM %(schema)s.ctags, %(schema)s.files, %(schema)s.versions, %(schema)s.packages \
     WHERE versions.package_id = packages.id \
     AND ctags.version_id = versions.id \
     AND ctags.file_id = files.id \
     ORDER BY packages.name, versions.vnumber, files.path, tag, line, kind, language \
     LIMIT 100",

    "metric":
    "SELECT packages.name, versions.vnumber, metric, value_ \
     FROM %(schema)s.metrics, %(schema)s.versions, %(schema)s.packages \
     WHERE versions.package_id = packages.id \
     AND metrics.sourceversion_id = versions.id \
     AND metric != 'size' \
     ORDER BY packages.name, versions.vnumber, metric \
     LIMIT 100",

    # XXX projecting also on the ctags column gives different result (by a few
    # units), even if the actual ctags tables are identical. WTH ?!?!
    "history_size":
    "SELECT suite, source_packages, binary_packages, source_files \
     FROM %(schema)s.history_size \
     ORDER BY timestamp, suite",

    "history_sloccount":
    "SELECT suite, \
       lang_ansic, lang_cpp, lang_lisp, lang_erlang, lang_python, lang_yacc \
     FROM %(schema)s.history_sloccount \
     ORDER BY timestamp, suite",
}



def pg_restore(dbname, dumpfile):
    subprocess.check_call(['pg_restore', '--no-owner', '--no-privileges',
                           '--dbname', dbname, dumpfile],
                          preexec_fn=subprocess_setup)

def pg_dump(dbname, dumpfile):
    subprocess.check_call(['pg_dump', '--no-owner', '--no-privileges', '-Fc',
                           '-f', dumpfile, dbname],
                          preexec_fn=subprocess_setup)

def pg_dropdb(dbname):
    subprocess.check_call(['dropdb', dbname],
                          preexec_fn=subprocess_setup)

def pg_createdb(dbname):
    subprocess.check_call(['createdb', dbname],
                          preexec_fn=subprocess_setup)

def db_setup(test_subj, dbname=TEST_DB_NAME, dbdump=TEST_DB_DUMP, echo=False):
    """Sets up the db for use by a given test subject.

    test_subj must be an instance of DbTestFixture (or inheritated class),
    or the class itself. This allows using db_setup by
    - unittest setUp (instance method), or
    - unittest setUpClass (class method).

    """
    try:
        pg_createdb(dbname)
    except subprocess.CalledProcessError:	# try recovering once, in case
        pg_dropdb(dbname)			# the db already existed
        pg_createdb(dbname)
    test_subj.dbname = dbname
    test_subj.db = sqlalchemy.create_engine(
        'postgresql:///' + dbname, echo=echo)
    pg_restore(dbname, dbdump)
    Session = sqlalchemy.orm.sessionmaker()
    test_subj.session = Session(bind=test_subj.db)

def db_teardown(test_subj):
    """Tears down db support used by a given test subject.

    test_subj must be an instance of DbTestFixture (or inheritated class), or
    the class itself. See db_setup for further discussion

    """
    test_subj.session.rollback()
    test_subj.session.close()
    test_subj.db.dispose()
    pg_dropdb(test_subj.dbname)


class DbTestFixture(object):
    """mix this in a given test subject to have DB fixture support"""

    def db_setup(self, dbname=TEST_DB_NAME, dbdump=TEST_DB_DUMP, echo=False):
        db_setup(self, dbname=TEST_DB_NAME, dbdump=TEST_DB_DUMP, echo=False)

    @classmethod
    def db_setup_cls(cls, dbname=TEST_DB_NAME, dbdump=TEST_DB_DUMP, echo=False):
        db_setup(cls, dbname=TEST_DB_NAME, dbdump=TEST_DB_DUMP, echo=False)

    def db_teardown(self):
        db_teardown(self)
    
    @classmethod
    def db_teardown_cls(cls):
        db_teardown(cls)