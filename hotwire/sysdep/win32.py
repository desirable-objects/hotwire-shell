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

import os,sys,re
_pathexts = os.environ.get('PATHEXT', '.com;.exe;.bat').split(';')
_win_exec_re_str = '(' + ('|'.join(map(lambda x: '(' + re.escape(x) + ')', _pathexts))) + ')$'
win_exec_re = re.compile(_win_exec_re_str, re.IGNORECASE)
# Better suggestions accepted!  This is used to try to find the entrypoint for a process.
win_dll_re = re.compile(r'\.((dll)|(DLL)|(drv)|(DRV))$')

# Hack - this is just to integrate better with things like Turbogears on Windows, we
# actually need a better way of extending the path
os.environ['PATH'] += r';c:\Python25\Scripts'

try:
    from ctypes import CDLL
    from ctypes.util import find_library
    msvcrt = CDLL(find_library("msvcrt"))
except:
    msvcrt = None
