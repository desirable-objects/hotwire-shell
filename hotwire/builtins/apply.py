# This file is part of the Hotwire Shell project API.

# Copyright (C) 2007,2008 Colin Walters <walters@verbum.org>

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

import os,sys,locale

from hotwire.builtin import builtin_hotwire, InputStreamSchema, MultiArgSpec
from hotwire.command import Pipeline,HotwireContext

@builtin_hotwire(options_passthrough=True,
                 input=InputStreamSchema('any'))
def apply(context, *args):
    _("""Like Unix xargs - take input and convert to arguments.""")

    newargs = list(args)
    for argument in context.input:
        if not isinstance(argument, basestring):
            argument = unicode(argument)
        newargs.append(argument)
        
    new_context = HotwireContext(initcwd=context.cwd)
    # TODO - pull in resolver from shell.py?  Should this function expand
    # aliases?        
    pipeline = Pipeline.create(new_context, None, *newargs)
    pipeline.execute_sync(assert_all_threaded=True)
    for result in pipeline.get_output():
        yield result
