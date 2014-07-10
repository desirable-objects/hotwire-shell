# This file is part of the Hotwire Shell project API.

# Copyright (C) 2007 Colin Walters <walters@verbum.org>

# Permission is hereby granted, free of charge, to any person obtaining a copy 
# of this software and associated documentation files (the "Software"), to deal 
# in the Software without restriction, including without limitation the rights 
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies 
# of the Software, and to permit persons to whom the Software is furnished to do so, 
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all 
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE X CONSORTIUM BE 
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, 
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR 
# THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os,sys,logging,time,datetime,threading
try:
    import sqlite3
except:
    from pysqlite2 import dbapi2 as sqlite3

import gobject

from hotwire.externals.singletonmixin import Singleton
from hotwire.sysdep.fs import Filesystem
from hotwire.logutil import log_except
#import processing

_logger = logging.getLogger("hotwire.State")

def _get_state_path(name):
    dirname = Filesystem.getInstance().make_conf_subdir('state')
    return os.path.join(dirname, name)

class CommandHistoryEntry(object):
    __slots__ = ['command', 'exectime']
    def __init__(self, cmd, exectime):
        self.command = cmd
        self.exectime = exectime

class History(Singleton):
    def __init__(self):
        super(History, self).__init__()
        self.__no_save = False
        self.__path = path = _get_state_path('history.sqlite')
        have_history = os.path.exists(path)
        _logger.debug("opening connection to history db: %s", path)
        self.__conn = sqlite3.connect(path, isolation_level=None)
        cursor = self.__conn.cursor()
        # Commands is the primary text input history table
        cursor.execute('''CREATE TABLE IF NOT EXISTS Commands (bid INTEGER PRIMARY KEY AUTOINCREMENT, cmd TEXT, exectime DATETIME, dirpath TEXT)''')     
        # Is there a way to do ALTER TABLE IF NOT DONE?
        try:
            # Transition from pre-0.700
            cursor.execute('''ALTER TABLE Commands ADD lang_uuid TEXT''')
            cursor.execute('''UPDATE Commands SET lang_uuid = ? WHERE lang_uuid IS NULL''', ('62270c40-a94a-44dd-aaa0-689f882acf34',))
        except sqlite3.OperationalError, e:
            pass
        # This was a pre-0.700 index.
        cursor.execute('''DROP INDEX IF EXISTS CommandsIndex''')
        cursor.execute('''CREATE INDEX IF NOT EXISTS CommandsIndex2 on Commands (cmd, lang_uuid)''')
        
        # Autoterm and Tokens were dropped
        
        # Records frequently used directories
        cursor.execute('''CREATE TABLE IF NOT EXISTS Directories (dbid INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, count INTEGER, modtime DATETIME)''')
        
        # Nothing in CmdInput yet...need to fix this.
        cursor.execute('''CREATE TABLE IF NOT EXISTS CmdInput (dbid INTEGER PRIMARY KEY AUTOINCREMENT, cmd TEXT, line TEXT, modtime DATETIME)''')
        cursor.execute('''CREATE INDEX IF NOT EXISTS CmdInputIndex on CmdInput (cmd, line, modtime)''')
        
        # Currently just used to note which persist tables have been converted        
        cursor.execute('''CREATE TABLE IF NOT EXISTS Meta (keyName TEXT UNIQUE, keyValue)''')
        
        if not have_history and os.path.exists(os.path.expanduser("~/.bash_history")):
            self.__run_async(self.__import_bash_history)

    def __import_bash_history(self, conn):
        try:
            f = open(os.path.expanduser("~/.bash_history"))
            now = datetime.datetime.now()
            cursor = conn.cursor()
            cursor.execute('''BEGIN TRANSACTION''')
            for line in f:
                line = line.rstrip() # strip the newline
                vals = (line, now, "/", "62270c40-a94a-44dd-aaa0-689f882acf34")
                _logger.debug("doing insert of %s", vals)
                cursor.execute('''INSERT INTO Commands VALUES (NULL, ?, ?, ?, ?)''', vals)
            cursor.execute('''COMMIT''')
        finally:
            f.close()

    def set_no_save(self):
        self.__no_save = True

    @log_except(_logger)
    def __do_run_async(self, func, args, kwargs):
        _logger.debug("in async run of %r", func)
        conn = sqlite3.connect(self.__path, isolation_level=None)
        try:
            func(conn, *args, **kwargs)
        finally:
            conn.close()

    def __run_async(self, func, *args, **kwargs):
        from hotwire.async import MiniThreadPool
        tp = MiniThreadPool.getInstance()
        tp.run(self.__do_run_async, args=(func, args, kwargs))
        
    def __do_append_command(self, conn, lang_uuid, cmd, cwd):
        cursor = conn.cursor()
        cursor.execute('''BEGIN TRANSACTION''')
        vals = (cmd, datetime.datetime.now(), cwd, lang_uuid)
        _logger.debug("doing insert of %s", vals)
        cursor.execute('''INSERT INTO Commands VALUES (NULL, ?, ?, ?, ?)''', vals)
        cursor.execute('''COMMIT''')
        self.__append_countitem('Directories', 'path', cwd, conn=conn)

    def append_command(self, lang_uuid, cmd, cwd):
        if self.__no_save:
            return
        # Run this in a timeout, because for some reason we seem to stutter while executing it;
        # This might be because sqlite is holding the Python lock so we can't do any processing.
        gobject.timeout_add(250, lambda: self.__run_async(self.__do_append_command, lang_uuid, cmd, cwd))
        
    def __search_limit_query(self, tablename, column, orderval, searchterm, limit, countmin=0, filters=[], distinct=False):
        queryclauses = []
        args = []        
        if searchterm:
            queryclauses.append(column + " LIKE ? ESCAPE '%'")
            args.append('%' + searchterm.replace('%', '%%') + '%')            
        if countmin > 0:
            queryclauses.append("count > %d " % (countmin,))
        queryclauses.extend(map(lambda x: x[0], filters))
        args.extend(map(lambda x: x[1], filters))
        if queryclauses:
            queryclause = ' WHERE ' + ' AND '.join(queryclauses)
        else:
            queryclause = ''
        sql = ((('SELECT %s * FROM %s' % (distinct and 'DISTINCT' or '', tablename,)) + queryclause + 
                  (' ORDER BY %s DESC LIMIT %d' % (orderval, limit,))),
                args)
        _logger.debug("generated search query: %s", sql)
        return sql
        
    def search_commands(self,  lang_uuid, searchterm, limit=50, **kwargs):
        cursor = self.__conn.cursor()
        if lang_uuid is not None:
            kwargs['filters'] = [(' lang_uuid = ? ', lang_uuid)]
        (sql, args) = self.__search_limit_query('Commands', 'cmd', 'exectime', searchterm, limit,
                                                **kwargs)
        _logger.debug("execute using args %s: %s", args, sql)
        for v in cursor.execute(sql, args):
            yield v[1]
        
    def __append_countitem(self, tablename, colname, value, conn=None):
        src_conn = conn or self.__conn
        cursor = src_conn.cursor()
        cursor.execute('''BEGIN TRANSACTION''')
        cursor.execute('''SELECT * FROM %s WHERE %s = ?''' % (tablename, colname), (value,))
        result = cursor.fetchone()
        if not result:
            current_count = 0
        else:
            current_count = result[2]
        _logger.debug("incrementing count %s", current_count)
        vals = (value, current_count+1, datetime.datetime.now())
        _logger.debug("doing insert of %s", vals)
        cursor.execute('''INSERT OR REPLACE INTO %s VALUES (NULL, ?, ?, ?)''' % (tablename,), vals)
        cursor.execute('''COMMIT''')
        
    def search_dir_usage(self, searchterm, limit=20):
        cursor = self.__conn.cursor()
        (sql, args) = self.__search_limit_query('Directories', 'path', 'count', searchterm, limit, countmin=4)
        for v in cursor.execute(sql, args):
            yield v[1:]
        
    def append_usage(self, colkey, *args, **kwargs):
        getattr(self, 'append_%s_usage' % (colkey,))(*args, **kwargs)
        
    def search_usage(self, colkey, *args, **kwargs):
        return getattr(self, 'search_%s_usage' % (colkey,))(*args, **kwargs)

    def search_command_input(self, cmd, searchterm, limit=20):
        cursor = self.__conn.cursor()
        (sql, args) = self.__search_limit_query('CmdInput', 'line', 'modtime', searchterm, limit,
                                                filters=[('cmd = ?', cmd)])         
        _logger.debug("execute using args %s: %s", args, sql)
        for v in cursor.execute(sql, args):
            yield v[2]
        
    def record_command_input(self, cmd, input):
        cursor = self.__conn.cursor()
        cursor.execute('''BEGIN TRANSACTION''')
        vals = (cmd, input, datetime.datetime.now())
        _logger.debug("doing insert of %s", vals)
        cursor.execute('''INSERT INTO CmdInput VALUES (NULL, ?, ?, ?)''', vals)
        cursor.execute('''COMMIT''')
    
_prefinstance = None
class Preferences(gobject.GObject):
    def __init__(self):
        super(Preferences, self).__init__()
        path = _get_state_path('prefs.sqlite')
        _logger.debug("opening connection to prefs db: %s", path)
        self.__conn = sqlite3.connect(path, isolation_level=None)
        self.__monitors = []
        
        cursor = self.__conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS Prefs (dbid INTEGER PRIMARY KEY AUTOINCREMENT, keyName TEXT UNIQUE, keyValue, modtime DATETIME)''')
 
    def get_pref(self, key, default=None):
        cursor = self.__conn.cursor()        
        result = cursor.execute('''SELECT keyValue from Prefs where keyName = ?''', (key,)).fetchone()
        if result is None:
            return default
        return result[0]
 
    def set_pref(self, key, value):
        (root, other) = key.split('.', 1)
        cursor = self.__conn.cursor()
        cursor.execute('''BEGIN TRANSACTION''')
        cursor.execute('''INSERT OR REPLACE INTO Prefs VALUES (NULL, ?, ?, ?)''', [key, value, datetime.datetime.now()])
        cursor.execute('''COMMIT''')
        self.__notify(key, value)
        
    def __notify(self, key, value):
        _logger.debug("doing notify for key %s new value: %s", key, value)
        for prefix, handler, args in self.__monitors:
            if key.startswith(prefix):
                try:
                    handler(self, key, value, *args)
                except:
                    _logger.error('Failed to invoke handler for preference %s', key, exc_info=True)
    
    def monitor_prefs(self, prefix, handler, *args):
        self.__monitors.append((prefix, handler, args))
    
    @staticmethod
    def getInstance():
        global _prefinstance
        if _prefinstance is None:
            _prefinstance = Preferences()
        return _prefinstance

_viewstateinstance = None
class ViewState(gobject.GObject):
    def __init__(self):
        super(ViewState, self).__init__()
        path = _get_state_path('viewstate.sqlite')
        _logger.debug("opening connection to viewstate db: %s", path)
        self.__conn = sqlite3.connect(path, isolation_level=None)
        self.__monitors = []
        
        cursor = self.__conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS ViewState (dbid INTEGER PRIMARY KEY AUTOINCREMENT, keyName TEXT UNIQUE, keyValue INTEGER, modtime DATETIME)''')
 
    def get_state(self, key, default=None):
        cursor = self.__conn.cursor()
        result = cursor.execute('''SELECT keyValue from ViewState where keyName = ?''', (key,)).fetchone()
        if result is None:
            return default
        return result[0]
 
    def set_state(self, key, value):
        _logger.debug("Set %s => %s" % (key, value))
        cursor = self.__conn.cursor()
        cursor.execute('''BEGIN TRANSACTION''')
        cursor.execute('''INSERT OR REPLACE INTO ViewState VALUES (NULL, ?, ?, ?)''', [key, value, datetime.datetime.now()])
        cursor.execute('''COMMIT''')
        self.__notify(key, value)
        
    def __notify(self, key, value):
        _logger.debug("doing notify for key %s new value: %s", key, value)
        for prefix, handler, args in self.__monitors:
            if key.startswith(prefix):
                try:
                    handler(self, key, value, *args)
                except:
                    _logger.error('Failed to invoke handler for preference %s', key, exc_info=True)
    
    def monitor_view_state(self, prefix, handler, *args):
        self.__monitors.append((prefix, handler, args))
    
    @staticmethod
    def getInstance():
        global _viewstateinstance
        if _viewstateinstance is None:
            _viewstateinstance = ViewState()
        return _viewstateinstance

__all__ = ['History','Preferences', 'ViewState']      
