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

from hotwire.builtin import Builtin, BuiltinRegistry, MultiArgSpec

class TermBuiltin(Builtin):
    __doc__ = _("""Execute a system command in a new terminal.""")
    def __init__(self):
        super(TermBuiltin, self).__init__('term',
                                          nodisplay=True,
                                          argspec=MultiArgSpec('args'),
                                          options_passthrough=True,
                                          threaded=False)

    def execute(self, context, args):
        if len(args) > 0 and args[0] == '-e':
            autoclose = True
            args = args[1:]
        else:
            autoclose = False
        context.hotwire.open_term(context.cwd, context.pipeline, args, window=True, autoclose=autoclose)
        return []
        
BuiltinRegistry.getInstance().register_hotwire(TermBuiltin())
