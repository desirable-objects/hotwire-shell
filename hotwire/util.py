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

import os, sys, traceback, shlex, string, platform
import fnmatch, commands
from xml.sax.saxutils import escape as escape_xml
import hotwire.unicodeutils
from hotwire.unicodeutils import get_unichar_category, is_category_letter, is_category_number

try:
    import threadframe
    have_threadframe = True
except:
    have_threadframe = False

def xmap(f, l):
  for x in l:
    yield f(x)

def assert_strings_equal(x, y):
  if x != y:
    raise AssertionError("%s != %s" % (x, y))

def markup_for_match(text, start, end, matchtarget=None):
    source = matchtarget or text
    return  '%s<b>%s</b>%s%s' % (escape_xml(source[0:start]),
                                 escape_xml(source[start:end]),
                                 escape_xml(source[end:]),
                                 matchtarget and (' - <i>' + text + '</i>') or '')
    


def _dump_threads(stream):
    """Built in in Python 2.5, needed for earlier versions"""
    for i,frame in enumerate(threadframe.threadframe()):
        stream.write('**** THREAD %d **** \n' % (i,))
        for line in traceback.format_stack(frame):
            stream.write(line)
    return True

_thread_idle_dump_id = 0
def start_thread_dump_task(timeout, stream):
    if not have_threadframe:
        return
    stop_thread_dump_task()
    _thread_idle_dump_id = gobject.timeout_add(timeout, _dump_threads, stream)

def stop_thread_dump_task():
    global _thread_idle_dump_id
    if _thread_idle_dump_id > 0:
        gobject.source_remove(_thread_idle_dump_id)
        _thread_idle_dump_id = 0

_kb = 1024.0
_mb = _kb*_kb
_gb = _mb*_kb
def format_file_size(bytes):
    if bytes < _kb:
        return "%d bytes" % (bytes,)
    elif bytes < _mb:
        return "%.1f KB" % (bytes/_kb,)
    elif bytes < _gb:
        return "%.1f MB" % (bytes/_mb,)
    else:
        return "%.1f GB" % (bytes/_gb,)

def tracefn(f):
    def _do_trace(*args, **kwargs):
        print "%s(%s %s)" %(f.func_name,args, kwargs)
        result = f(*args, **kwargs)
        print "=> %s" % (result,)
        return result
    return _do_trace

def quote_arg(arg):
    """Quote arg for processing by a shell.
    If arg would pass through unquoted, return unmodified arg."""
    if not isinstance(arg, unicode):
        arg = unicode(arg, 'utf-8')
    safechars = '.,/~_-+:'
    safeonly = True
    safe_space_only = True
    def is_letter_or_number(c):
        return is_category_letter(c) or is_category_number(c)
    for c in arg:
        cat = get_unichar_category(c)
        if (not is_letter_or_number(cat)) and c not in safechars:
            safeonly = False
            if c != ' ':
                safe_space_only = False
    if safeonly:
        return arg
    if safe_space_only:
        return arg.replace(' ', '\\ ')
    return quote_shell_arg(arg)

# FIXME - is this right?
def quote_shell_arg(cmd):
  return commands.mkarg(cmd)

def ellipsize(buf, l):
    """Return a possibly-truncated version of buf to maximum length l, adding
    ellipsis if the string is truncated."""
    if l < 4:
        l = 4
    if len(buf) >= l:
        buf = buf[:l-3] + '...'
    return buf

def class_is_assignable(target, src):
    """Return whether or not src is a subclass of target."""
    def compatible_types(cls, seen):
        compat = [cls]
        for i in cls.__bases__:
            if i not in seen:
                compat.extend(compatible_types(i, seen=compat))
        return compat

    return target in compatible_types(src, [])
