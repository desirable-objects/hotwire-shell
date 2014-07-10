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

import os,sys,shutil,stat,logging,tempfile,urllib
from cStringIO import StringIO

import hotwire
from hotwire.fs import unix_basename, FilePath, path_expanduser, path_fromurl, path_tourl, atomic_rename, iterd_sorted
from hotwire.async import MiniThreadPool
from hotwire.logutil import log_except
from hotwire.gutil import call_idle
from hotwire.sysdep import is_windows, is_unix
from hotwire.externals.singletonmixin import Singleton
import hotwire.sysdep.fs_impl
from hotwire.externals.dispatch import dispatcher

_logger = logging.getLogger("hotwire.sysdep.Filesystem")

class BaseFilesystem(object):
    def __init__(self):
        self.fileklass = File
        self._override_conf_dir = None
        self._trashdir = os.path.expanduser('~/.Trash')
        self.makedirs_p(self._trashdir)

    def ls_dir(self, dir, show_all):
        for x in iterd_sorted(dir):
            fobj = self.get_file_sync(x)
            if show_all or (not fobj.hidden):  
                yield fobj

    def get_basename_is_ignored(self, bn):
        return False
    
    def get_monitor(self, path, cb):
        raise NotImplementedError()
    
    def get_bookmarks(self):
        return BaseBookmarks.getInstance()

    def get_file(self, path):
        f = self.fileklass(path, fs=self)
        f.get_stat()
        return f
    
    def get_file_sync(self, path):
        f = self.fileklass(path, fs=self)
        f.get_stat_sync()
        return f
        
    def launch_open_file(self, path, cwd=None):
        raise NotImplementedError()

    def launch_edit_file(self, path):
        raise NotImplementedError()

    def get_file_menuitems(self, file_obj, context=None):
        return []

    def get_conf_dir(self):
        if self._override_conf_dir:
            target = self._override_conf_dir
        else:
            target = self._get_conf_dir_path()
        return self.makedirs_p(target)
    
    def get_system_conf_dir(self):
        if self._override_conf_dir:
            return None
        try:
            syspath = self._get_system_conf_dir_path()
        except NotImplementedError, e:
            return None
        return syspath 
        
    def _get_conf_dir_path(self):
        raise NotImplementedError()

    def _get_system_conf_dir_path(self):
        raise NotImplementedError()
    
    def set_override_conf_dir(self, path):
        self._override_conf_dir = path
    
    def make_conf_subdir(self, *args):
        path = os.path.join(self.get_conf_dir(), *args)
        return self.makedirs_p(path)
    
    def get_path_generator(self):
        raise NotImplementedError()

    def executable_on_path(self, execname):
        for dpath in self.get_path_generator():
            epath = FilePath(execname, dpath)
            try:
                fobj = self.get_file_sync(epath)
            except FileStatError, e:
                continue            
            if fobj.is_executable:
                return epath
        return False

    def path_executable_match(self, input, file_path):
        raise NotImplementedError()

    def move_to_trash(self, path):
        bn = unix_basename(path)
        newf = os.path.join(self._trashdir, bn)
        try:
            statbuf = os.stat(newf) 
        except OSError, e:
            statbuf = None
        if statbuf:
            _logger.debug("Removing from trash: %s", newf) 
            if stat.S_ISDIR(statbuf.st_mode):
                shutil.rmtree(newf, onerror=lambda f,p,e:_logger.exception("Failed to delete '%s' from trash", newf))
        shutil.move(path, newf)

    def get_trash_item(self, name):
        return os.path.join(self._trashdir, name)

    def undo_trashed(self, args):
        for arg in args:
            trashed = self.get_trash_item(unix_basename(arg))
            if trashed:
                shutil.move(trashed, arg)

    def makedirs_p(self, path):
        try:
            os.makedirs(path)
        except OSError, e:
            # hopefully it was EEXIST...
            pass
        return path
    
    def supports_owner(self):
        return False
    
    def supports_group(self):
        return False
    
class FileStatError(Exception):
    def __init__(self, cause):
        Exception.__init__(self, str(cause))
        self.cause = cause

class File(object):
    """An extended crossplatform stat() container, essentially.  
    Extra data retrieved includes symbolic link target (if applicable) and icon."""
    
    path = property(lambda self: self._path, doc="""Complete path to file, expressed in Hotwire notation (always forward slashes)""")
    uri = property(lambda self: self._uri, doc="""URI notation for file""")
    basename = property(lambda self: self._basename, doc="""Name of file (without directory component)""")
    size = property(lambda self: self._get_size(), doc="""Size in bytes of file, or None if unknown""")
    hidden = property(lambda self: self._hidden, doc="""Whether or not this file is normally visible in directory listings""")
    icon = property(lambda self: self._icon, doc="""Icon name (internal Hotwire/GTK+ representation)""")
    is_directory = property(lambda self: self.test_directory(), doc="""Whether or not this object represents a directory""")
    is_executable = property(lambda self: self._is_executable(), doc="""Whether or not this object represents an OS-executable file""")
    is_link = property(lambda self: self._is_link(), doc="""Whether or not this object represents a symbolic link""")
    file_type_char = property(lambda self:self._get_file_type_char(), doc="""Unix-style file type character ('d' for directory, etc.)""")
    stat_mode = property(lambda self: self._get_stat_mode(), doc="""Unix-style access mode""")
    permissions_string = property(lambda self: self._get_permissions_string(), doc="""Unix-style compact permissions string""")
    mtime = property(lambda self: self._get_mtime(), doc="""Modification time, in seconds since the epoch""")
    mimetype = property(lambda self: self._get_mime(), doc="""MIME type""")

    __slots__ = ['fs', 'stat', 'xaccess', 'icon_error', '_permstring', 'target_stat', 'stat_error']
    def __init__(self, path, fs=None):
        super(File, self).__init__()
        if not isinstance(path, unicode):
            path = unicode(path, 'utf-8')
        self._path = path
        self._uri = 'file://' + urllib.pathname2url(path.encode(sys.getfilesystemencoding()))
        self._basename = unix_basename(path)
        self.fs = fs
        self.stat = None
        self.xaccess = None
        self._hidden = None
        self._icon = None
        self.icon_error = False
        self._permstring = None
        self.target_stat = None
        self.stat_error = None
        
    def __cmp__(self, o):
        if isinstance(o, File):
            return cmp(self.path, o.path)
        return cmp(self.path, o)

    def test_directory(self, follow_link=True):
        if not self.stat:
            return False
        if follow_link and stat.S_ISLNK(self.stat[stat.ST_MODE]):
            stbuf = self.target_stat
        else:
            stbuf = self.stat
        return stbuf and stat.S_ISDIR(stbuf[stat.ST_MODE])
    
    def _is_link(self):
        return self.stat and stat.S_ISLNK(self.stat[stat.ST_MODE])
    
    def _is_executable(self):
        return self.xaccess

    def _get_size(self):
        if self.stat and stat.S_ISREG(self.stat[stat.ST_MODE]):
            return self.stat[stat.ST_SIZE]
        return None

    def _get_mtime(self):
        if self.stat:
            return self.stat[stat.ST_MTIME]
        return None
    
    def _get_file_type_char(self):
        if self.is_directory:
            return 'd'
        return '-'
    
    def _get_stat_mode(self):
        return self.stat[stat.ST_MODE]

    def _get_permissions_string(self):
        if self._permstring:
            return self._permstring
        
        perms = self.stat_mode
        if not perms:
            return
        buf = StringIO()
                
        buf.write(self.file_type_char)
        
        if perms & stat.S_ISUID: buf.write('s')
        elif perms &stat.S_IRUSR: buf.write('r')
        else: buf.write('-')
        if perms & stat.S_IWUSR: buf.write('w')
        else: buf.write('-')
        if perms & stat.S_IXUSR: buf.write('x')
        else: buf.write('-')
        
        if perms & stat.S_ISGID: buf.write('s')
        elif perms & stat.S_IRGRP:buf.write('r')
        else: buf.write('-')
        if perms & stat.S_IWGRP: buf.write('w')
        else: buf.write('-')
        if perms & stat.S_IXGRP: buf.write('x')
        else: buf.write('-')
        
        if perms & stat.S_IROTH: buf.write('r')
        else: buf.write('-')
        if perms & stat.S_IWOTH: buf.write('w')
        else: buf.write('-')
        if perms & stat.S_IXOTH: buf.write('x')
        else: buf.write('-')
        
        self._permstring = buf.getvalue()
        return self._permstring
    
    def _get_mime(self):
        return None

    def get_stat(self):
        self._get_stat_async()

    def _get_stat_async(self):
        MiniThreadPool.getInstance().run(self.__get_stat_signal)
        
    def get_stat_sync(self):
        self._do_get_stat(rethrow=True)
        self._do_get_xaccess()
        self._do_get_hidden()
        self._do_get_icon()

    def _do_get_stat(self, rethrow=False):
        try:
            self.stat = hasattr(os, 'lstat') and os.lstat(self.path) or os.stat(self.path)
            if stat.S_ISLNK(self.stat[stat.ST_MODE]):
                try:
                    self.target_stat = os.stat(self.path)
                except OSError, e:
                    self.target_stat = None		
        except OSError, e:
            _logger.debug("Failed to stat '%s': %s", self.path, e)
            self.stat_error = str(e)
            if rethrow:
                raise FileStatError(e)
            
    def _do_get_xaccess(self):
        self.xaccess = os.access(self.path, os.X_OK)
        
    def _do_get_hidden(self):
        pass 
        
    def _do_get_icon(self):
        if not self.stat:
            self._icon = 'gtk-dialog-error'
        elif self.is_directory:
            self._icon = 'gtk-directory'
        else:
            self._icon = 'gtk-file'

    @log_except(_logger)
    def __get_stat_signal(self):
        self.get_stat_sync()
        call_idle(self.__idle_emit_changed, priority=gobject.PRIORITY_LOW)        
        
    @log_except(_logger)
    def __idle_emit_changed(self):
        responses = dispatcher.send(sender=self)
        _logger.debug("idle changed dispatch from %r, responses=%r", self, responses)
        
class BaseBookmarks(Singleton):
    def __init__(self):
        self.__bookmarks_path = path_expanduser('~/.gtk-bookmarks')
        try:
            self.__monitor = Filesystem.getInstance().get_monitor(self.__bookmarks_path, self.__on_bookmarks_changed)
        except NotImplementedError, e:
            pass
        self.__bookmarks = []
        self.__read_bookmarks()
        
    def add(self, path):
        if path in self.__bookmarks:
            return
        self.__bookmarks.append(path) 
        (bdir, bname) = os.path.split(self.__bookmarks_path)
        (fd, temppath) = tempfile.mkstemp('.tmp', bname, bdir)
        f = os.fdopen(fd, 'w')
        for mark in self.__bookmarks:
            f.write(path_tourl(mark))
            f.write('\n')
        f.close()
        atomic_rename(temppath, self.__bookmarks_path)  
        # Might as well signal now             
        dispatcher.send(sender=self)
        
    @log_except(_logger)
    def __on_bookmarks_changed(self, *args):
        self.__read_bookmarks()
        dispatcher.send(sender=self)
        
    def __read_bookmarks(self):
        try:
            f = open(self.__bookmarks_path)
        except IOError, e: 
            _logger.debug("failed to open bookmarks", exc_info=True)
            return
        self.__bookmarks = map(lambda x: path_fromurl(x).strip(), f)
        f.close()
        
    def __iter__(self):
        for b in self.__bookmarks:
            yield b

_module = None
if is_unix():
    try:
        import hotwire.sysdep.fs_impl.fs_gnomevfs
        _module = hotwire.sysdep.fs_impl.fs_gnomevfs
    except:
        import hotwire.sysdep.fs_impl.fs_unix
        _module = hotwire.sysdep.fs_impl.fs_unix
elif is_windows():
    import hotwire.sysdep.fs_impl.fs_win32
    _module = hotwire.sysdep.fs_impl.fs_win32
else:
    raise NotImplementedError("No Filesystem implemented for this platform")

_instance = None
class Filesystem(object):
    @staticmethod
    def getInstance():
        global _instance
        if _instance is None:
            _instance = _module.getInstance()
        return _instance
