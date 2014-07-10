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

import os, sys, fnmatch, stat, shutil
import posixpath, locale, urllib, codecs

import hotwire
from hotwire.async import MiniThreadPool
from hotwire.externals.glob2 import iglob
from hotwire.sysdep import is_windows, is_unix

def dirglob(dir, pat):
    for result in iglob(pat, dir):
        yield result

_sep_len = len(os.sep)
def unix_basename(path):
    if path.endswith(os.sep):
        path = path[:-_sep_len]
    return os.path.basename(path)

def path_unabs(path, base):
    """Convert path into a relative path using base as the base directory."""
    if path.startswith(base):
        if len(path) > len(base) and path[len(base)] == '/':
            return path[len(base)+1:]
        return path[len(base):]
    return path

def path_fromurl(url):
    """Return a local pathname from a file:// URL."""
    if url.startswith('file://'):
        url = url[7:]
    return urllib.unquote(url)

def path_tourl(path):
    """Return a file:// URL for a pathname."""
    return 'file://' + urllib.quote(path)

path_fastnormalize = lambda x: x
path_normalize = os.path.normpath
path_expanduser = os.path.expanduser
path_join = posixpath.join
path_abs = os.path.abspath
path_dirname = posixpath.dirname
def win32_normpath(path):
  ret = win32_fast_normpath(os.path.normpath(path))
  if path.endswith('/') and not ret.endswith('/'): #normpath might eat the ending '/'
      ret += '/'
  return ret
def win32_fast_normpath(path):
  path = path.replace('\\', '/')
  if path[1:3] == ':\\':
    path = path[0] + ':/' + path[2:]
  return path
def win32_expanduser(path):
  return win32_fast_normpath(os.path.expanduser(path))
def win32_pathjoin(*args):
  return path_fastnormalize(os.path.join(*args))
def win32_abspath(path):
  return path_fastnormalize(os.path.abspath(path))
if is_windows():
    path_fastnormalize = win32_fast_normpath
    path_normalize = win32_normpath
    path_expanduser = win32_expanduser
    path_join = win32_pathjoin
    path_abs = win32_abspath

_homepath = os.path.expanduser("~")
def path_unexpanduser(path):
    # Don't unexpand ~ because it looks plain and ugly
    if (path != _homepath) and path.startswith(_homepath):
        path = '~' + path[len(_homepath):]
    return path

def copy_file_or_dir(src, dest, dest_is_dir):
    stbuf = os.stat(src) 
    dest_target = dest_is_dir and posixpath.join(dest, unix_basename(src)) or dest
    if src == dest_target:
        return
    if stat.S_ISDIR(stbuf.st_mode):
        shutil.copytree(src, dest_target)
    elif stat.S_ISLNK(stbuf.st_mode):
        symtarget = os.readlink(src)
        os.symlink(dest_target, symtarget)
    else:
        shutil.copy(src, dest_target)

def open_text_file(path, mode='r', buffering=None):
    """Return a file object that reads or writes to a locale-encoded text file."""
    (lcode, locale_encoding) = locale.getdefaultlocale()
    kwargs={}
    if buffering is not None:
        kwargs['buffering'] = buffering
    return codecs.open(path, mode, locale_encoding, 'strict', **kwargs)

def file_is_valid_utf8(path):
    f = open(path, 'rb')
    buf = f.read(8192)
    # is there a faster way
    try:
        unicode(buf, 'utf-8').encode('utf-8')
    except UnicodeDecodeError, e:
        f.close()
        return False
    f.close()
    return True

class FilePath(unicode):
    """Represents a path to a file; can be treated as a string.
       This class should have been built into Python."""
    def __new__(cls, value, dir=None):
        if not isinstance(value, unicode):
            value = unicode(value, 'utf-8')
        if not os.path.isabs(value) and dir:
            value = path_fastnormalize(posixpath.join(dir, value))
        inst = super(FilePath, cls).__new__(cls, value)
        return inst

    def path_join(self, path):
        return posixpath.join(self, path)
    
def iterd(dpath, fpath=False):
    """Generate full path names of files in directory named by dpath."""
    dpath = unicode(dpath)
    entries = os.listdir(dpath)
    if fpath:
        for fname in entries:
            yield FilePath(fname, dpath)
    else:
        for fname in entries:
            yield path_join(dpath, fname)
        
def iterd_sorted(dpath, **kwargs):
    for v in sorted(iterd(dpath, **kwargs), locale.strcoll):
        yield v

def atomic_rename(oldp, newp):
    # FIXME - not really atomic on Windows =/
    if is_windows():
        if os.access(newp, os.R_OK):
            os.unlink(newp)
    os.rename(oldp, newp)
