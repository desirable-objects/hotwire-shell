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

import os,sys,re,subprocess,sha,tempfile

from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema, OutputStreamSchema, ArgSpec

from hotwire.fs import path_join
from hotwire.sysdep.fs import Filesystem

class PyFilterBuiltin(Builtin):
    __doc__ = _("""Filter object list using Python code.""")
 
    PYFILTER_CONTENT = '''
import os,sys,re
def execute(context, input):
  for it in input:
    if %s:
      yield it''' 
    def __init__(self):
        super(PyFilterBuiltin, self).__init__('py-filter',
                                              argspec=(ArgSpec('expression'),),
                                              input=InputStreamSchema('any'),
                                              output='identity')

    def execute(self, context, args, options=[]):
        buf = self.PYFILTER_CONTENT % (args[0],)
        code = compile(buf, '<input>', 'exec')
        locals = {}
        exec code in locals
        execute = locals['execute']
        custom_out = execute(context, context.input)
        if custom_out is None:
            return
        if hasattr(custom_out, '__iter__'):
            for o in custom_out:
                yield o
        else:
            yield custom_out

BuiltinRegistry.getInstance().register_hotwire(PyFilterBuiltin())
