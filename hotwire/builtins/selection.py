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

from hotwire.builtin import Builtin, BuiltinRegistry, OutputStreamSchema, ArgSpec

class SelectionBuiltin(Builtin):
    __doc__ = _("""With no arguments, returns currently selected objects.
Single integer argument selects object at that index.""")
    def __init__(self):
        super(SelectionBuiltin, self).__init__('selection', 
                                               aliases=['sel'],
                                               argspec=(ArgSpec('index', opt=True),),
                                               threaded=False,
                                               output=OutputStreamSchema('any', 
                                                                         typefunc=lambda hotwire: hotwire.get_current_output_type()))

    def execute(self, context, args):
        current = context.hotwire.snapshot_current_selected_output()        
        if len(args) == 0:
            if current is None:
                return
            for obj in current.value:
                yield obj
        elif len(args) == 1:
            idx = int(args[0])
            for i,obj in enumerate(current.value):
                if i == idx:
                    yield obj
                    return
            raise ValueError(_("Index %d out of range") % (idx,))
        elif len(args) > 2:
            raise ValueError(_("Too many arguments specified"))            
    
BuiltinRegistry.getInstance().register_hotwire(SelectionBuiltin())
