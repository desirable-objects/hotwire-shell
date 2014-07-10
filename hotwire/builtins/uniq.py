# This file is part of the Hotwire Shell project API.

# Copyright (C) 2008 Hamish Downer <mishd@fastmail.fm>

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

from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema, ArgSpec

class UniqBuiltin(Builtin):
    __doc__ = _("""Let through only unique items dropping duplicates, optionally matching on a property.  The item/property being matched must be immutable (string, tuple etc).""")
    def __init__(self):
        super(UniqBuiltin, self).__init__('uniq',
                                            input=InputStreamSchema('any'),
                                            output='any',
                                            options=[['-c', '--count']],
                                            argspec=(ArgSpec('property', opt=True),))

    def execute(self, context, args, options=[]):     
        if len(args) == 1:
            target_prop = args[0]
        else:
            target_prop = None
        count_obj = '-c' in options
        order_unique_items = []
        unique_items = {}
        for arg in context.input:
            if target_prop is not None:
                value = getattr(arg, target_prop)
            else:
                value = arg
            if value in unique_items:
                if count_obj:
                    unique_items[value] += 1
                continue
            unique_items[value] = 1
            if count_obj:
                # keep order while counting
                order_unique_items.append(value)
            else:
                yield value
        if count_obj:
            for item in order_unique_items:
                yield (unique_items[item], item)
                        

BuiltinRegistry.getInstance().register_hotwire(UniqBuiltin())
