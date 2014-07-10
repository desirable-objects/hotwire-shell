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

import os,sys,imp,logging

import hotwire
from hotwire.fs import iterd
from hotwire.sysdep.fs import Filesystem

_logger = logging.getLogger("hotwire.PluginSystem")

def load_plugins():
    fs = Filesystem.getInstance()
    syspath = fs.get_system_conf_dir()
    if syspath:
        sys_pluginpath = os.path.join(syspath, 'plugins')
        _load_plugins_in_dir(sys_pluginpath)
    custom_path = fs.makedirs_p(os.path.join(fs.get_conf_dir(), "plugins"))
    _load_plugins_in_dir(custom_path)
   
def _load_plugins_in_dir(dirname):
    if not os.path.isdir(dirname):
       return    
    _logger.debug("loading from plugin path: %s", dirname)   
    for f in iterd(dirname):
        if f.endswith('.py'):
            fname = os.path.basename(f[:-3])
            try:
                _logger.debug("Attempting to load plugin: %s", f)
                (stream, path, desc) = imp.find_module(fname, [dirname])
                try:
                    module = imp.load_module(fname, stream, f, desc)
                    _logger.debug("Plugin loaded successfully %s", module)                    
                finally:
                    stream.close()
            except:
                _logger.warn("Failed to load custom file: %s", f, exc_info=True)
                
 