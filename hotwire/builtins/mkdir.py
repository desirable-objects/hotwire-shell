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

import os, sys, shutil, stat

import hotwire
import hotwire.fs
from hotwire.fs import FilePath

from hotwire.builtin import Builtin, BuiltinRegistry, MultiArgSpec
from hotwire.builtins.fileop import FileOpBuiltin

class MkdirBuiltin(FileOpBuiltin):
    __doc__ = _("""Create directories.""")
    def __init__(self):
        super(MkdirBuiltin, self).__init__('mkdir',
                                           hasstatus=True,
                                           argspec=MultiArgSpec('paths', min=1))

    def execute(self, context, args):
        sources_total = len(args)
        for i,arg in enumerate(args):
            arg_path = FilePath(arg, context.cwd)
            try:
                os.makedirs(arg_path)
            except OSError, e:
                pass
            self._status_notify(context, sources_total, i+1)

        return []
BuiltinRegistry.getInstance().register_hotwire(MkdirBuiltin())
