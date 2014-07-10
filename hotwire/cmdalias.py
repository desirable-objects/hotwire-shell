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

import os,sys,re,stat,logging

from hotwire.externals.singletonmixin import Singleton

_logger = logging.getLogger("hotwire.CmdAlias")

class Alias(object):
    def __init__(self, name, target):
        self.name = name
        self.target = target

class AliasRegistry(Singleton):
    def __init__(self):
        self.__aliases = {}

    def remove(self, name):
        del self.__aliases[name]
    
    def insert(self, name, value):
        if not isinstance(value, Alias):
            value = Alias(name, value)
        self.__aliases[name] = value

    def __getitem__(self, item):
        return self.__aliases[item]

    def __iter__(self):
        for x in self.__aliases.itervalues():
            yield x
 