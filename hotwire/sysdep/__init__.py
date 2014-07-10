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

import os,sys

if sys.platform.startswith('java'):
    import java
    osname = java.lang.System.getProperty('os.name')
    _is_jython = True
else:
    import platform
    osname = platform.system()
    _is_jython = False
_is_unix = osname in ('Linux', 'FreeBSD', 'Darwin')
_is_windows = osname in ('Windows', 'Microsoft')
_is_linux = osname == 'Linux'

def is_jython():
    return _is_jython

def is_windows():
    return _is_windows

def is_unix():
    return _is_unix

def is_linux():
    return _is_linux

# These files are the right place to do global, platform-specific early
# initialization and share code between different components in this tree.
if is_unix():
    import hotwire.sysdep.unix
elif is_windows():
    import hotwire.sysdep.win32
