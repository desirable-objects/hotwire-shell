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

class StringMatch(MarkupText):
    def __new__(cls, value, match):
        inst = super(StringMatch, cls).__new__(cls, value)
        inst.match = match
        inst.add_markup('b', match.start(), match.end())
        return inst

class FilterBuiltin(Builtin):
    __doc__ = _("""Filter input objects by regular expression, matching on a property (or repr)""")
    def __init__(self):
        super(FilterBuiltin, self).__init__('filter',
                                            input=InputStreamSchema('any'),
                                            output='identity',
                                            options=[['-s', '--stringify'], ['-i', '--ignore-case'],['-v', '--invert-match']],
                                            argspec=('regexp', ArgSpec('property', opt=True)))

    def execute(self, context, args, options=[]):     
        if len(args) == 2:
            prop = args[1]
        else:
            prop = None
        regexp = args[0]
        target_prop = prop
        invert = '-v' in options
        stringify = '-s' in options
        compiled_re = re.compile(regexp, (('-i' in options) and re.IGNORECASE or 0) | re.UNICODE)
        for arg in context.input:
            if target_prop is not None:
                target_propvalue = getattr(arg, target_prop)
            else:
                target_propvalue = arg
            if not isinstance(target_propvalue, basestring):
                if not stringify:
                    raise ValueError(_("Value not a string: %r" % (target_propvalue,)))
                else:
                    target_propvalue = repr(target_propvalue)
            elif not isinstance(target_propvalue, unicode):
                target_propvalue = unicode(target_propvalue, 'utf-8')                
                        
            match = compiled_re.search(target_propvalue)
            if invert:
                match = not match
            if match:
                if isinstance(arg, str):
                    yield StringMatch(target_propvalue, match)
                else:
                    yield arg
BuiltinRegistry.getInstance().register_hotwire(FilterBuiltin())
