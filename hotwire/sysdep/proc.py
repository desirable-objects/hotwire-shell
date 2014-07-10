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

import sys,os,logging,platform,time

from hotwire.sysdep import is_windows, is_unix, is_linux

class BaseProcessManager(object):
    def __init__(self):
        super(BaseProcessManager, self).__init__()
        self.__proc_snapshot_time = None
        self.__proc_snapshot = []
    
    def get_extra_subproc_args(self):
        return {}

    def get_processes(self):
        raise NotImplementedError()

    def get_cached_processes(self, timeout_secs=2):
        curtime = time.time()
        if self.__proc_snapshot_time is None or self.__proc_snapshot_time+timeout_secs < curtime:
            self.__proc_snapshot = list(self.get_processes())
            self.__proc_snapshot_time = curtime
        return self.__proc_snapshot

    def terminate_pidgroup(self, pid):
        raise NotImplementedError()

    def kill_pid(self, pid):
        raise NotImplementedError()
    
    def get_self(self):
        pid = os.getpid()
        for proc in self.get_processes():
            if proc.pid == pid:
                return proc
        return None    

class Process(object):
    __slots__ = ['pid', 'cmd', 'owner_name']
    def __init__(self, pid, cmd, owner_name):
        self.pid = pid
        self.cmd = cmd
        self.owner_name = owner_name

    def kill(self):
        raise NotImplementedError()

    def __cmp__(self, o):
        if isinstance(o, Process):
            return cmp(self.pid, o.pid)
        return cmp(self.pid, o)

    def __str__(self):
        return "Process '%s' (%s) of %s" % (self.cmd, self.pid, self.owner_name)

_module = None
if is_linux():
    import hotwire.sysdep.proc_impl.proc_linux
    _module = hotwire.sysdep.proc_impl.proc_linux
elif is_unix():
    import hotwire.sysdep.proc_impl.proc_unix
    _module = hotwire.sysdep.proc_impl.proc_unix
elif is_windows():
    import hotwire.sysdep.proc_impl.proc_win32
    _module = hotwire.sysdep.proc_impl.proc_win32
else:
    raise NotImplementedError("No Process implemented for %r" % (platform.system(),))

_instance = None
class ProcessManager(object):
    @staticmethod
    def getInstance():
        global _instance
        if _instance is None:
            if not _module:
                raise NotImplementedError("Couldn't find a process implementation")
            _instance = _module.getInstance()
        return _instance
