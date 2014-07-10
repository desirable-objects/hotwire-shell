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

import os,sys,subprocess,logging, stat

from hotwire.fs import path_normalize, unix_basename
from hotwire.sysdep.fs import File, BaseFilesystem,iterd_sorted, FileStatError
from hotwire.sysdep.win32 import win_exec_re, msvcrt
import win32api, win32con
import os.path

from win32com.shell import shell,shellcon
import gtk
try:
    import ctypes
    from ctypes import CDLL
    from ctypes.util import find_library
    cgtk= CDLL(find_library("libgtk-win32-2.0-0.dll"))
    cgdk = CDLL(find_library("libgdk-win32-2.0-0.dll"))
    cgdk_pixbuf = CDLL(find_library("libgdk_pixbuf-2.0-0.dll"))
except:
    cgtk = None
    cgdk = None
    cgdk_pixbuf = None
    
_logger = logging.getLogger("hotwire.sysdep.Win32Filesystem")

if msvcrt != None:
    from ctypes import Structure, c_uint, c_ushort, c_short, c_long, byref
    class Stat32(Structure):
        _fields_ = [("st_dev", c_uint),
                    ("st_ino", c_ushort),
                    ("st_mode", c_ushort),
                    ("st_nlink", c_short),
                    ("st_uid", c_short),
                    ("st_gid", c_short),
                    ("st_rdev", c_uint),
                    ("st_size", c_long),
                    ("st_atime", c_long),
                    ("st_mtime", c_long),
                    ("st_ctime", c_long)];

# TODO - implement native "Recycle Bin" trash functionality.
# involves lots of hackery with shellapi
class Win32Filesystem(BaseFilesystem):
    def __init__(self):
        super(Win32Filesystem, self).__init__()
        self.fileklass = Win32File

    def ls_dir(self, dir, show_all):
        for x in iterd_sorted(dir):
            try:
                if show_all:
                    yield self.get_file_sync(x)
                else:
                    if not (win32api.GetFileAttributes(x)
                            & win32con.FILE_ATTRIBUTE_HIDDEN):
                        yield self.get_file_sync(x)
            except:
                # An exception here can happen on Windows if the file was in
                # use.
                # See http://code.google.com/p/hotwire-shell/issues/detail?id=126
                _logger.debug("Failed to stat %r", x, exc_info=True)
                pass

    def _get_conf_dir_path(self):
        return os.path.expanduser(u'~/Application Data/hotwire')

    def get_path_generator(self):
        pathenv = os.environ['PATH']
        # TODO - what encoding is PATHENV in? 
        for d in pathenv.split(u';'):
            yield d
        
    def get_basename_is_ignored(self, bn):
        # FIXME - extend this to use Windows systems
        return False        

    def path_executable_match(self, input, file_path):
        """On Windows; we want to allow for e.g. using "python" as an exact match 
        for "python.exe"."""           
        input_basename = unix_basename(input)
        file_basename = unix_basename(file_path)
        if input_basename == file_basename:
            return True
        (pfx, ext) = os.path.splitext(file_basename)
        return input_basename == pfx

    def launch_open_file(self, path, cwd=None):
        try:
            win32api.ShellExecute(0, "open", path.encode(sys.getfilesystemencoding()), None, None, 1)
        except:
            raise NotImplementedError()
    
class Win32File(File):
    def __init__(self, *args, **kwargs):
        super(Win32File, self).__init__(*args, **kwargs)
        
    def _do_get_xaccess(self):
        super(Win32File, self)._do_get_xaccess()
        self.xaccess = self.xaccess and win_exec_re.search(self.path)

    def _do_get_hidden(self):
        path = self.path.encode(sys.getfilesystemencoding()).rstrip('/')#FindFiles on directories ending with '/' returns []
        files = win32api.FindFiles(path) #FindFIles might return multiple files,
                                         #if the path contains a wild character '*' or '?'.
                                         #However, '*' or '?' is not a valid character for file name on Win32.
                                         #So, there should be only 0 or 1 file returned here.
        if len(files) == 0:
            self._hidden = None
            return
        if len(files) > 1:
            raise Exception("OOPS: More than 1 files matched. A wildcharacter in filename?")
        self._hidden = bool(files[0][0] & win32con.FILE_ATTRIBUTE_HIDDEN)

    def _do_get_stat(self, rethrow=False):
        try:
            super(Win32File, self)._do_get_stat(rethrow)
        except FileStatError, e:
            _logger.debug("Failed to stat '%s': %s", self.path, e)
            if msvcrt != None:
                _logger.debug("Trying our own wrapper of _stat32")
                st = Stat32()
                msvcrt._stat(self.path.encode(sys.getfilesystemencoding()), byref(st))
                self.stat = (st.st_mode, st.st_ino, st.st_dev, st.st_nlink - 1, st.st_uid,
                             st.st_gid, st.st_size, st.st_atime, st.st_mtime, st.st_ctime)
            else:
                if rethrow:
                    raise

    def _get_mime(self):
        if self.is_directory:
            return 'x-directory/normal'
        try:
            extname = os.path.splitext(self.path)[-1]
            hkey = win32api.RegOpenKeyEx(win32con.HKEY_CLASSES_ROOT, extname, 0, win32con.KEY_READ)
            return win32api.RegQueryValueEx(hkey, 'Content Type')[0]
        except:
            return None
                
    def _do_get_icon(self):
        sys_encoded_path = self.path.encode(sys.getfilesystemencoding())
        sys_encoded_path = sys_encoded_path.replace('/', '\\') #SHGetFileInfo doesn't work with Unix style paths
        ret, info = shell.SHGetFileInfo(sys_encoded_path, 0, shellcon.SHGFI_ICONLOCATION, 0)
        if ret and (info[1] or info[3]):
            icon = 'gtk-win32-shell-icon;%s;%d' %(info[3], info[1])
        else:
            icon = 'gtk-win32-shell-icon;%s' % sys_encoded_path
        icon_theme = gtk.icon_theme_get_default()
        if not icon_theme.has_icon(icon) and not self.__create_builtin_icon(icon, sys_encoded_path):
            super(Win32File, self)._do_get_icon()
        else:
            self._icon = icon
        
    def __create_builtin_icon(self, icon_name, filepath):
        if not cgtk or not cgdk or not cgdk_pixbuf:
            return False
        icon_flags = [shellcon.SHGFI_SMALLICON, shellcon.SHGFI_LARGEICON]
        for flag in icon_flags:
            try:
                ret, info = shell.SHGetFileInfo(filepath, 0, shellcon.SHGFI_ICON|flag, 0)
                if ret:
                    pixbuf = cgdk.gdk_win32_icon_to_pixbuf_libgtk_only(info[0])#a private function in gdk
                    if pixbuf:
                        cgtk.gtk_icon_theme_add_builtin_icon(icon_name, cgdk_pixbuf.gdk_pixbuf_get_height(pixbuf), pixbuf)
                        return True
            except:
                continue
        return False
    
def getInstance():
    return Win32Filesystem()
