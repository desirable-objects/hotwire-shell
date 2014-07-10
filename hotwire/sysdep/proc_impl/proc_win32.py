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

import os,sys,logging,string

from hotwire.sysdep.proc import BaseProcessManager, Process
from hotwire.sysdep.win32 import win_exec_re, win_dll_re

import win32process,win32api,win32security,win32con,ntsecuritycon

_logger = logging.getLogger('hotwire.proc.Win32')

class WindowsProcess(Process):
    def __init__(self, pid):
        ph = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION|win32con.PROCESS_VM_READ,0,pid)
        token = win32security.OpenProcessToken(ph, win32con.TOKEN_QUERY)
        sid,attr = win32security.GetTokenInformation(token, ntsecuritycon.TokenUser)
        (username, proc_domain, proc_type) = win32security.LookupAccountSid(None, sid)
        exes = []
        modules = []
        for module in win32process.EnumProcessModules(ph):
            fn = win32process.GetModuleFileNameEx(ph, module)
            if win_exec_re.search(fn):
                exes.append(fn)        
            else:
                modules.append(fn)
        # gross but...eh
        if not exes:
            nondll = []
            for mod in modules:
                if not win_dll_re.search(mod):
                    nondll.append(mod)
            if nondll:
                exes.append(nondll[0])
        super(WindowsProcess, self).__init__(pid, string.join(exes, ' '), username)

class Win32ProcessManager(BaseProcessManager):
    def get_processes(self):
        for pid in win32process.EnumProcesses():
            if pid > 0:
                try:
                    yield WindowsProcess(pid) 
                except:
                    #_logger.exception("Couldn't get process information for pid %d", pid)
                    continue

    def terminate_pidgroup(self, pid):
        # FIXME - is this enough?  Is there a notion of process groups on win32?
        self.kill_pid(pid)

    def kill_pid(self, pid):
        ph = win32api.OpenProcess(win32con.PROCESS_TERMINATE|win32con.PROCESS_QUERY_INFORMATION,0,pid)
        win32api.TerminateProcess(ph, 0)

def getInstance():
    return Win32ProcessManager()
