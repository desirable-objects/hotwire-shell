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

import os,sys,platform,logging

import hotwire
from hotwire.sysdep import is_windows, is_unix

_logger = logging.getLogger("hotwire.sysdep.Ipc")

class BaseIpc(object):
    def singleton(self):
        raise NotImplementedError()

    def register_window(self, win):
        raise NotImplementedError()

    def raise_existing(self):
        raise NotImplementedError()
    
    def run_command(self, cwd, *args):
        raise NotImplementedError()

_module = None
if is_unix():
    import hotwire.sysdep.ipc_impl.ipc_dbus
    _module = hotwire.sysdep.ipc_impl.ipc_dbus
else:
    raise NotImplementedError("No Ipc implemented for %s!" % (platform.system(),))

_instance = None
class Ipc(object):
    @staticmethod
    def getInstance():
        global _instance
        if _instance is None:
            _instance = _module.getInstance()
        return _instance
