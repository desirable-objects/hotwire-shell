# This file is part of the Hotwire Shell project API.

# Copyright (C) 2008 Colin Walters <walters@verbum.org>

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

from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema

class StringifyBuiltin(Builtin):
    __doc__ = _("""Convert output to a string.""")
    def __init__(self):
        super(StringifyBuiltin, self).__init__('stringify',
                                               input=InputStreamSchema('any'),
                                               output=str,
                                               argspec=None)

    def execute(self, context, args, options=[]):
        if len(args) != 0:
            raise ValueError(_("Too many arguments specified"))
        for arg in context.input:
            if not isinstance(arg, basestring):
                yield str(arg)
            else:
                yield arg
BuiltinRegistry.getInstance().register_hotwire(StringifyBuiltin())
