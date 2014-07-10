# This file is part of the Hotwire Shell project API.

# Copyright (C) 2008 Kevin Kubasik <kevin@kubasik.net>
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

import os,sys,re

from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema, ArgSpec

class ReplaceBuiltin(Builtin):
    __doc__ = _("""Replace input objects by regular expression, matching on a property (or repr)""")
    def __init__(self):
        super(ReplaceBuiltin, self).__init__('replace',
                                            input=InputStreamSchema('any'),
                                            output='identity',
                                            argspec=(ArgSpec('regexp'), ArgSpec('replacement')))

    def execute(self, context, args, options=[]):
        regexp = args[0]
        replacement = args[1]
        stringify = '-s' in options
        compiled_re = re.compile(regexp, (('-i' in options) and re.IGNORECASE or 0) | re.UNICODE)
        for arg in context.input:
            yield compiled_re.sub(regexp,replacement,arg)
BuiltinRegistry.getInstance().register_hotwire(ReplaceBuiltin())
