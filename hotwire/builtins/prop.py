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

import re

from hotwire.text import MarkupText
from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema, ArgSpec

class PropBuiltin(Builtin):
    __doc__ = _("""Return the property of an object.""")
    def __init__(self):
        super(PropBuiltin, self).__init__('prop',
                                          input=InputStreamSchema('any'),
                                          output='any',
                                          idempotent=True,
                                          argspec=(ArgSpec('name'),),
                                          options=[['-t', '--tuple']],
                                          threaded=True)

    def execute(self, context, args, options=[]):
        prop = args[0]            
        target_prop = prop
        tuplify = '-t' in options
        for arg in context.input:
            target_propvalue = getattr(arg, target_prop)
            if tuplify:
                yield (arg, target_propvalue)
            else:
                yield target_propvalue
BuiltinRegistry.getInstance().register_hotwire(PropBuiltin())
