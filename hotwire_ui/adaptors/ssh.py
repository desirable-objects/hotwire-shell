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

import os,sys,subprocess

from hotwire.builtin import Builtin, BuiltinRegistry, MultiArgSpec
from hotwire.externals.singletonmixin import Singleton
from hotwire.completion import Completer, Completion
from hotwire.sysdep.fs import Filesystem
from hotwire.sshutil import OpenSSHKnownHosts       
        
class OpenSshKnownHostCompleter(Completer):
    def __init__(self):
        super(OpenSshKnownHostCompleter, self).__init__()
        self.__hosts = OpenSSHKnownHosts.getInstance()    

    def completions(self, text, cwd, **kwargs):
        for host in self.__hosts.get_hosts():
            compl = self._match(host, text, None, icon='gtk-network')
            if compl: yield compl

class HotSshBuiltin(Builtin):
    __doc__ =  _("""Open a connection via SSH.""")
    def __init__(self):
        super(HotSshBuiltin, self).__init__('ssh', 
                                            nodisplay=True,
                                            argspec=MultiArgSpec('args', min=1),
                                            options_passthrough=True)

    def get_completer(self, context, args, i):
        return OpenSshKnownHostCompleter()

    def execute(self, context, args, options=[]):
        # TODO replace this with SysBuiltin
        argv = ['hotwire-ssh']
        argv.extend(args)
        newenv = dict(os.environ)
        newenv['DESKTOP_STARTUP_ID'] = 'START_TIME%s' % (context.gtk_event_time,)
        subprocess.Popen(argv, env=newenv)
        return []
        
BuiltinRegistry.getInstance().register_hotwire(HotSshBuiltin())
