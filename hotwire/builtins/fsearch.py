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

import os, sys, logging, re

import hotwire
import hotwire.fs
from hotwire.fs import FilePath, file_is_valid_utf8, open_text_file

from hotwire.command import HotwireContext
from hotwire.builtin import Builtin, BuiltinRegistry, ArgSpec
from hotwire.builtins.fileop import FileOpBuiltin
from hotwire.sysdep.fs import Filesystem, FileStatError

_logger = logging.getLogger("hotwire.builtins.FSearch")

class FileStringMatch(object):
    """Result of a "grep" like operation on a file."""
    
    path = property(lambda self: self._path, doc="""Path to matched file.""")
    line = property(lambda self: self._line, doc="""Matched line value.""")
    line_num = property(lambda self: self._line_num, doc ="""Matched line number.""")
    match_start = property(lambda self: self._match_start, doc="""Index of match beginning.""")
    match_end = property(lambda self: self._match_end, doc="""Index of match end.""")    
    
    def __init__(self, path, line, line_num, match_start, match_end):
        self._path = path
        self._line = line
        self._line_num = line_num
        self._match_start = match_start
        self._match_end = match_end

class FSearchBuiltin(FileOpBuiltin):
    __doc__ = _("""Search directory tree for files matching a regular expression.""")
    def __init__(self):
        super(FSearchBuiltin, self).__init__('fsearch',
                                             output=FileStringMatch,
                                             argspec=('regexp', ArgSpec('directory', opt=True)),                                             
                                             options=[['-i', '--ignore-case']])

    def execute(self, context, args, options=[]):       
        regexp = args[0]
        if len(args) == 2:
            path = args[1]
        else:
            path = context.cwd
        regexp = args[0]
        comp_regexp = re.compile(regexp, (('-i' in options) and re.IGNORECASE or 0) | re.UNICODE)
        walk_builtin = BuiltinRegistry.getInstance()['walk']
        newctx = HotwireContext(context.cwd)
        for fobj in walk_builtin.execute(newctx, [path]):
            fp = None
            try:
                fp = open_text_file(fobj.path) 
                for i,line in enumerate(fp):
                    match = comp_regexp.search(line)
                    if match:
                        yield FileStringMatch(fobj.path, line[:-1], i, match.start(), match.end())
                fp.close()
            except OSError, e:
                pass
            except UnicodeDecodeError, e:
                pass
BuiltinRegistry.getInstance().register_hotwire(FSearchBuiltin())
