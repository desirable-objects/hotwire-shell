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

import os

from hotwire.sysdep import is_jython

if is_jython():
    getpwuid = lambda x: 'nobody'
    getgrgid = lambda x: 'nobody'
else:        
    from pwd import getpwuid
    from grp import getgrgid

os.environ['HOTWIRE_SHELL'] = '1'

# Ensure subprocesses don't try to treat us as a full tty
os.environ['TERM'] = 'dumb'
# Fix Fedora and probably other systems
standard_admin_paths = ['/sbin', '/usr/sbin']
path_elts = os.environ['PATH'].split(':')  
path_fixed = False
for path in standard_admin_paths:
    if not path in path_elts:
        path_fixed = True
        path_elts.append(path)
if path_fixed:
    os.environ['PATH'] = ':'.join(path_elts)

# Work around git bug
os.environ['GIT_PAGER'] = 'cat'

# This is stupid; Unix should just do this.
_pwuid_cache = {}
def getpwuid_cached(uid):
    try:
        return _pwuid_cache[uid]
    except KeyError, e:
        _pwuid_cache[uid] = result = getpwuid(uid)
        return result

_grgid_cache = {}
def getgrgid_cached(gid):
    try:
        return _grgid_cache[gid]
    except KeyError, e:
        _grgid_cache[gid] = result = getgrgid(gid)
        return result
