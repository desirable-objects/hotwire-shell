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

import os,signal,logging

from hotwire.sysdep.proc import Process, BaseProcessManager

_logger = logging.getLogger("hotwire.proc.Unix")

class UnixProcess(Process):
    def kill(self):
        UnixProcessManager._kill_pid(self.pid)

class UnixProcessManager(BaseProcessManager):
    @staticmethod
    def signal_pid_recurse(pid, signum):
        """This function should be used with caution."""
        try:
            pgid = os.getpgid(pid)
            try:
                os.killpg(pgid, signum)
                return # This hopefully worked, just return
            except OSError, e:
                _logger.warn("failed to send sig %s to process group %d", signum, pgid, exc_info=True)
        except OSError, e:
            _logger.warn("failed to get process group for %d", pid, exc_info=True)
            pgid = None
        # Ok, we failed to kill the process group; fall back to the pid itself
        try:
            os.kill(pid, signum)
            return True
        except OSError, e:
            _logger.debug("Failed to send sig %s to pid %d", signum, pid)
            return False    
    
    def terminate_pidgroup(self, pid):
        # THis is a bit racy...need to fix.  However for backwards compatibility
        # it's best to send SIGHUP as well as SIGTERM.  In some special cases like
        # setuid subprograms Unix allows SIGHUP but nothing else.
        UnixProcessManager.signal_pid_recurse(pid, signal.SIGHUP)        
        UnixProcessManager.signal_pid_recurse(pid, signal.SIGKILL)

    def kill_pid(self, pid):
        UnixProcessManager._kill_pid(pid)

    @staticmethod
    def _kill_pid(pid):
        try:
            os.kill(pid, signal.SIGKILL)
            return True
        except OSError, e:
            _logger.debug("Failed to kill pid '%d': %s", pid, e)
            return False

def getInstance():
    return UnixProcessManager()