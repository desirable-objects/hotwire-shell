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

import os, sys, os.path, stat, logging, locale
from itertools import imap

from hotwire.builtin import builtin_hotwire, InputStreamSchema, MultiArgSpec
from hotwire.fs import FilePath
from hotwire.sysdep.fs import Filesystem,File
from hotwire.util import xmap

_logger = logging.getLogger("hotwire.builtins.ls")

@builtin_hotwire(aliases=['dir'],
                 input=InputStreamSchema(str, optional=True),
                 output=File,
                 idempotent=True,
                 argspec=MultiArgSpec('paths'),
                 options=[['-l', '--long'],['-a', '--all'],['-i', '--input']])
def ls(context, *args):
    _("""List contents of a directory.""")
    show_all = '-a' in context.options
    long_fmt = '-l' in context.options
    process_input = '-i' in context.options
    fs = Filesystem.getInstance()
        
    if process_input and input is not None:
        args = list(args)
        args.extend(context.input)        
        
    if len(args) == 0:
        for x in fs.ls_dir(context.cwd, show_all):
            yield x
    elif len(args) == 1:
        path = FilePath(args[0], context.cwd)
        fobj = fs.get_file_sync(path)
        if fobj.is_directory:
            for x in fs.ls_dir(path, show_all):
                yield x
        else:
            yield fobj
            return      
    else:
        # Generate list of sorted File objects from arguments 
        for x in sorted(xmap(lambda arg: fs.get_file_sync(FilePath(arg, context.cwd)), args), 
                        lambda a,b: locale.strcoll(a.path, b.path)):
            yield x
