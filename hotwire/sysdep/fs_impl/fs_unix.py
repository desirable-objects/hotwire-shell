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

import os,sys,stat

from hotwire.fs import unix_basename
from hotwire.sysdep.fs import BaseFilesystem, File
from hotwire.sysdep.unix import getpwuid_cached, getgrgid_cached

class UnixFilesystem(BaseFilesystem):
    def __init__(self):
        super(UnixFilesystem, self).__init__()
        self.fileklass = UnixFile         
        
    def _get_conf_dir_path(self):
        return os.path.expanduser(u'~/.hotwire')

    def _get_system_conf_dir_path(self):
        return u'/etc/hotwire'

    def get_path_generator(self):
        for d in os.environ['PATH'].split(u':'):
            yield d

    def path_executable_match(self, input, file_path):
        """This function is a hack for Windows; essentially we
        allow using "python" as an exact match for "python.exe".
        This implementation is suitable for Unix systems
        where executability is determined by permissions mode
        and not extension."""        
        return unix_basename(input) == unix_basename(file_path)
    
    def supports_owner(self):
        return True
    
    def supports_group(self):
        return True
        
class UnixFile(File): 
    """A bare Unix file abstraction, using just the builtin Python methods."""
    
    owner = property(lambda self: self._get_uid(), doc="""Owner UID""")
    group = property(lambda self: self._get_gid(), doc="""Group GID""")
    owner_name = property(lambda self: self._get_owner(), doc="""Owner name""")
    group_name = property(lambda self: self._get_group(), doc="""Group name""")    
    
    def __init__(self, *args, **kwargs):
        super(UnixFile, self).__init__(*args, **kwargs)
  
    def _get_uid(self):
        return self.stat and self.stat.st_uid
    
    def _get_gid(self):
        return self.stat and self.stat.st_gid
    
    def _get_file_type_char(self):
        stmode = self.stat_mode
        if stat.S_ISREG(stmode): return '-'
        elif stat.S_ISDIR(stmode): return 'd'
        elif stat.S_ISLNK(stmode): return 'l'
        else: return '?'
        
    def _do_get_hidden(self):
        self._hidden = self.basename.startswith('.')        
    
    def _get_owner(self):
        uid = self.owner
        if uid is None:
            return
        try:
            return getpwuid_cached(uid).pw_name
        except KeyError, e:
            return str(uid)

    def _get_group(self):
        gid = self.group
        if gid is None:
            return
        try:
            return getgrgid_cached(gid).gr_name
        except KeyError, e:
            return str(gid)         

def getInstance():
    return UnixFilesystem()
