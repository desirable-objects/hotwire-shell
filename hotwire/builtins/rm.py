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

import os, shutil
from itertools import imap

import hotwire
from hotwire.fs import FilePath, unix_basename
from hotwire.sysdep.fs import Filesystem, File

from hotwire.builtin import BuiltinRegistry, InputStreamSchema, MultiArgSpec
from hotwire.builtins.fileop import FileOpBuiltin

class RmBuiltin(FileOpBuiltin):
    __doc__ = _("""Move a file to the trash.""")
    def __init__(self):
        super(RmBuiltin, self).__init__('rm', aliases=['delete'],
                                        input=InputStreamSchema(File, optional=True),
                                        undoable=True,
                                        hasstatus=True,
                                        argspec=MultiArgSpec('path'),
                                        options=[['-u', '--unlink'],['-r', '--recursive'],['-f', '--force']])

    def execute(self, context, args, options=[]):
        if len(args) == 0 and context.input is None:
            raise ValueError(_("Must specify at least one file"))
        mkfile = lambda arg: FilePath(arg, context.cwd)
        sources = map(mkfile, args)
        if context.input is not None:
            sources.extend(imap(lambda f: f.path, context.input)) 
        sources_total = len(sources)
        undo_targets = []
        self._status_notify(context, sources_total, 0)
        fs = Filesystem.getInstance()
        recursive = '-r' in options
        force = '-f' in options
        if '-u' in options:
            for i,arg in enumerate(sources):
                if recursive:
                    shutil.rmtree(arg, ignore_errors=force)
                else:
                    try:
                        os.unlink(arg)
                    except:
                        if not force:
                            raise
                self._status_notify(context,sources_total,i+1)                
            return []
        else:
            try:
                for i,arg in enumerate(sources):
                    try:
                        fs.move_to_trash(arg)
                    except:
                        if not force:
                            raise
                    undo_targets.append(arg)
                    self._status_notify(context,sources_total,i+1)
                    self._note_modified_paths(context, sources)
            finally:
                context.push_undo(lambda: fs.undo_trashed(undo_targets))
        return []
BuiltinRegistry.getInstance().register_hotwire(RmBuiltin())
