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

import os, sys, stat

from hotwire.script import script
from hotwire.builtin import Builtin, BuiltinRegistry, ArgSpec
from hotwire.fs import FilePath
from hotwire.sysdep.fs import File
from hotwire.completion import PathCompleter

if '_' not in globals(): globals()['_'] = lambda x: x

class CdCompleter(PathCompleter):
    def __init__(self):
        super(CdCompleter, self).__init__()
        
    def completions(self, text, cwd, **kwargs):
        for completion in super(CdCompleter, self).completions(text, cwd, **kwargs):
            fobj = completion.target
            if fobj.test_directory(follow_link=True):
                yield completion

class CdBuiltin(Builtin):
    __doc__ = _("""Change working directory and list its contents.""")
    def __init__(self):
        super(CdBuiltin, self).__init__('cd',
                                        output=File,
                                        idempotent=True,
                                        argspec=(ArgSpec('directory', opt=True),))

    def get_completer(self, context, args, i):
        return CdCompleter()

    def execute(self, context, args):
        if not args:
            target_dir = os.path.expanduser("~")
        else:
            target_dir = args[0]
        new_dir = context.hotwire.chdir(target_dir)
        pipeline = script('ls', new_dir)
        pipeline.execute_sync()
        for result in pipeline.get_output():
            yield result
BuiltinRegistry.getInstance().register_hotwire(CdBuiltin())
