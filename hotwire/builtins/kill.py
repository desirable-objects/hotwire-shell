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

import os,sys,signal
from itertools import imap

import hotwire

from hotwire.sysdep.proc import ProcessManager, Process
from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema, MultiArgSpec
from hotwire.externals.singletonmixin import Singleton
from hotwire.completion import Completer, Completion

_signals = []
for sym in dir(signal):
    if sym.startswith('SIG') and sym != 'SIG_DFL' and sym != 'SIG_IGN':
        _signals.append((sym, getattr(signal, sym)))
# This is kind of wasteful, but eh.  Death before inconvenience and all that.
_sigsym_to_value = {}
_sigvalue_to_sym = {}
for sym,num in _signals:
    _sigsym_to_value[sym[3:]] = num
    _sigvalue_to_sym[num] = sym

class ProcessCompleter(Completer):
    def __init__(self):
        super(ProcessCompleter, self).__init__() 

    def completions(self, text, cwd, **kwargs):
        proclist = ProcessManager.getInstance().get_cached_processes()         
        try:
            textint = int(text)
        except ValueError, e:
            textint = None   
        if textint is not None:
            for proc in proclist:
                pidstr = str(proc.pid)
                if pidstr.startswith(text):
                    yield Completion(pidstr[len(text):], proc, pidstr)
        else:
            pass
#            for proc in proclist:
#                idx = proc.cmd.find(text)
#                if idx >= 0:
#                    yield Completion(proc.cmd, idx, len(text), exact=False, default_icon='gtk-execute')

class KillBuiltin(Builtin):
    __doc__ = _("""Send a signal to a process.""")
    def __init__(self):
        super(KillBuiltin, self).__init__('kill',
                                          nodisplay=True,
                                          input=InputStreamSchema(Process, optional=True),
                                          options_passthrough=True,
                                          argspec=MultiArgSpec('pid', min=1))
        
    def get_completer(self, context, args, i):
        return ProcessCompleter()        

    def execute(self, context, args):
        signum = signal.SIGTERM
        sigidx = -1
        for i,arg in enumerate(args):
            if not arg.startswith('-'):
                continue
            optval = arg[1:]
            if optval in _sigsym_to_value:
                signum = _sigsym_to_value[optval]
                sigidx = i
                break
            else:
                optnum = int(optval)
                if optnum in _sigvalue_to_sym:
                    signum = optnum
                    sigidx = i
                    break
                else:
                    raise ValueError("Invalid signal number: %d", optnum)
        if sigidx >= 0:
            del args[sigidx]
        for arg in imap(int, args):
            os.kill(arg, signum)
        if context.input is not None:
            for arg in context.input:
                os.kill(arg.pid, signum)
        return []
        
BuiltinRegistry.getInstance().register_hotwire(KillBuiltin())
