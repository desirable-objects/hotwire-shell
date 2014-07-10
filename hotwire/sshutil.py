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

import os,sys,logging

from hotwire.sysdep.fs import Filesystem
from hotwire.externals.singletonmixin import Singleton
from hotwire.externals.dispatch import dispatcher
from hotwire.gutil import call_idle_once

_logger = logging.getLogger("hotwire.SshUtil")

class OpenSSHKnownHosts(Singleton):
    def __init__(self):
        super(OpenSSHKnownHosts, self).__init__()
        self.__path = os.path.expanduser('~/.ssh/known_hosts')
        self.__monitor = None
        self.__hostcache = None
        
    def __on_hostchange(self):
        try:
            _logger.debug("reading %s", self.__path)
            f = open(self.__path)
        except:
            _logger.debug("failed to open known hosts")
            f = None
        hosts = set()
        if f is not None:
            for line in f:
                hostip,rest = line.split(' ', 1)
                if hostip.find(',') > 0:
                    host = hostip.split(',', 1)[0]
                else:
                    host = hostip
                host = host.strip()
                hosts.add(host)
            f.close()
        self.__hostcache = hosts
        _logger.debug("ssh cache: %r", self.__hostcache)     
        # Do this in an idle to avoid recursion   
        call_idle_once(lambda: dispatcher.send(sender=self))
        
    def get_hosts(self):
        if self.__monitor is None:
            self.__monitor = Filesystem.getInstance().get_monitor(self.__path, self.__on_hostchange)            
        if self.__hostcache is None:
            self.__on_hostchange()
        return self.__hostcache
