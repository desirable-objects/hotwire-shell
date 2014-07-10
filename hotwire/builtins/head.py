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

import os,sys,pickle

from hotwire.fs import path_join, open_text_file
from hotwire.builtin import builtin_hotwire, InputStreamSchema

@builtin_hotwire(input=InputStreamSchema('any',optional=True),
                 options_passthrough=True,
                 idempotent=True)
def head(context, *files):
    _("""Return a subset of items from start of input stream.""")
    count = 10
    countidx = -1
    # Create a copy so we can delete from it safely
    files = list(files)
    for i,arg in enumerate(files):
        if arg.startswith('-'):
            count = int(arg[1:])
            countidx = i
            break
    if countidx >= 0:
        del files[countidx]
    if context.input is not None:
        for i,value in enumerate(context.input):
            if i >= count:
                break
            yield value
    for fpath in files:
        fpath = path_join(context.cwd, fpath)
        f = None
        f = open_text_file(fpath)
        for i,line in enumerate(f):
            if i>= count:
                break
            yield line
        f.close()
