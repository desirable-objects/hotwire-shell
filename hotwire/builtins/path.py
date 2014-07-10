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

from hotwire.text import MarkupText
from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema, ArgSpec

class PathBuiltin(Builtin):
    __doc__ = _("""Display or modify the external program execution path.""")
    def __init__(self):
        super(PathBuiltin, self).__init__('path',
                                          output=str,
                                          argspec=(ArgSpec('path', opt=True),),
                                          options=[['-a', '--prefix'], ['-s', '--suffix'], ['-d', '--del']],
                                          threaded=False)

    def execute(self, context, args, options=[]):
        curval = os.environ['PATH']
        if len(args) == 0:
            return curval
        if len(options) > 1:
            raise ValueError(_("At most one option can be specified"))
        arg = args[0]
        elts = curval.split(os.pathsep)
        if '-d' in options:
            if arg not in elts:
                raise ValueError(_("Not in path: %s") % (arg,))
            elts.remove(arg)
        elif '-a' in options:
            elts.insert(0, arg)
        elif '-s' in options:
            elts.append(arg)
        else: 
            assert False
        os.environ['PATH'] = os.pathsep.join(elts)    
        return os.environ['PATH']
BuiltinRegistry.getInstance().register_hotwire(PathBuiltin())
