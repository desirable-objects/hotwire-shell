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
from hotwire.fs import FilePath, file_is_valid_utf8, path_join

from hotwire.builtin import Builtin, BuiltinRegistry, ArgSpec
from hotwire.builtins.fileop import FileOpBuiltin
from hotwire.sysdep.fs import Filesystem, File, FileStatError

_logger = logging.getLogger("hotwire.builtins.Walk")

class WalkBuiltin(FileOpBuiltin):
    __doc__ = _("""Recursively traverse directory tree.""")
    def __init__(self):
        super(WalkBuiltin, self).__init__('walk',
                                          output=File,
                                          argspec=(ArgSpec('directory', opt=True),),
                                          options=[['-a', '--all']])

    def execute(self, context, args, options=[]):
        fs = Filesystem.getInstance()
        if len(args) == 1:
            path = path_join(context.cwd, args[0])
        else:
            path = context.cwd
        if '-a' not in options:
            ignorecheck = True
        else:
            ignorecheck = False 
        for (dirpath, subdirs, fnames) in os.walk(path):
            filtered_dirs = []
            if ignorecheck:
                for i,dpath in enumerate(subdirs):
                    try:
                        dstat = fs.get_file_sync(dpath)
                        if dstat.hidden:
                            filtered_dirs.append(i)
                    except FileStatError, e:
                        continue
                for c,i in enumerate(filtered_dirs):
                    del subdirs[i-c]
            for fname in fnames:
                fpath = path_join(dirpath, fname)                
                fobj = fs.get_file_sync(fpath)
                if ignorecheck and fobj.hidden:
                    continue
                yield fobj

BuiltinRegistry.getInstance().register_hotwire(WalkBuiltin())
