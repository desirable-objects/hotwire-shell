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


from hotwire.text import MarkupText
from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema, ArgSpec, MultiArgSpec 

class SortKey(object):
    def __init__(self, proplist):
        super(SortKey, self).__init__()
        self.proplist = proplist

    def __call__(self, x):
        li = []
        for prop in self.proplist:
            li.append(getattr(x,prop))
        return li

class SortBuiltin(Builtin):
    __doc__ = _("""Sort input objects by property (if defined) or using default python sorting""")
    def __init__(self):
        super(SortBuiltin, self).__init__('sort',
                                            input=InputStreamSchema('any'),
                                            output='identity',
                                            options=[['-r', '--reverse']],
                                            argspec=MultiArgSpec('property', min=0))

    def execute(self, context, args, options=[]):     
        reversesearch = '-r' in options
        outlist = list(context.input)
        if len(args) == 0:
            outlist.sort(reverse = reversesearch)
        elif len(args) == 1:
            outlist.sort(key = lambda x: getattr(x, args[0]), reverse = reversesearch)
        else:
            outlist.sort(key = SortKey(args), reverse = reversesearch)
        for arg in outlist:
            yield arg

BuiltinRegistry.getInstance().register_hotwire(SortBuiltin())
