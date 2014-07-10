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

from hotwire.builtin import Builtin, BuiltinRegistry, ArgSpec

from hotwire.completion import BuiltinCompleter

class HelpItem(object):
    def __init__(self, items):
        self.items = items

class HelpBuiltin(Builtin):
    __doc__ = _("""Display help.""")
    def __init__(self):
        super(HelpBuiltin, self).__init__('help',
                                          output=HelpItem,
                                          argspec=(ArgSpec('builtin', opt=True),))

    def get_completer(self, context, args, i):
        return BuiltinCompleter()

    def execute(self, context, args):
        builtins = BuiltinRegistry.getInstance()        
        yield HelpItem([builtins[x] for x in args])
            
    
BuiltinRegistry.getInstance().register_hotwire(HelpBuiltin())
