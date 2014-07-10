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

import os,sys,re,string, pwd

from hotwire.sysdep.proc_impl.proc_unix import UnixProcessManager, UnixProcess
from hotwire.sysdep.unix import getpwuid_cached, getgrgid_cached

_pwdcache = {}

_uid_re = re.compile(r'^Uid:\s+(\d+)')

class LinuxProcess(UnixProcess):
    """Representation of a Linux operating system process; information is gathered
from the /proc filesystem."""
    def __init__(self, pid):
        bincmd = file(os.path.join('/proc', str(pid), 'cmdline'), 'rb').read()
        self.arguments = bincmd.split('\x00') 
        owner_uid = -1
        for line in file(os.path.join('/proc', str(pid), 'status')):
            match = _uid_re.search(line)
            if match:
                owner_uid = int(match.group(1))
        super(LinuxProcess, self).__init__(pid, string.join(self.arguments, ' '), getpwuid_cached(owner_uid).pw_name)

class LinuxProcessManager(UnixProcessManager):
    def get_processes(self):
        num_re = re.compile(r'\d+')
        for d in os.listdir('/proc'):
            if num_re.match(d):
                try:
                    yield LinuxProcess(int(d))
                except OSError, e:
                    # Ignore processes that go away as we read them
                    pass
                except IOError, e:
                    pass
                
def getInstance():
    return LinuxProcessManager()
