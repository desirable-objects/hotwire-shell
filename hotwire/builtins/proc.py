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

import hotwire

from hotwire.sysdep.proc import ProcessManager, Process
from hotwire.builtin import Builtin, BuiltinRegistry

class PsBuiltin(Builtin):
    __doc__ = _("""List processes.""")
    def __init__(self):
        super(PsBuiltin, self).__init__('proc',
                                        output=Process,
                                        idempotent=True,
                                        argspec=None,
                                        options=[['-a', '--all'],])

    def execute(self, context, args, options=[]):
        myself_only = '-a' not in options        
        pm = ProcessManager.getInstance()
        if not myself_only:
            for proc in pm.get_processes():
                yield proc
        else:
            selfproc = pm.get_self()
            selfname = selfproc.owner_name            
            for proc in pm.get_processes():
                if proc.owner_name != selfname:
                    continue
                yield proc
BuiltinRegistry.getInstance().register_hotwire(PsBuiltin())
