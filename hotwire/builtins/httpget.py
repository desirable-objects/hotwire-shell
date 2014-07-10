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

import os,sys,httplib
from httplib import HTTPResponse
from StringIO import StringIO

from hotwire.fs import FilePath

from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema, ArgSpec

class HttpGetBuiltin(Builtin):
    __doc__ = _("""Perform a HTTP GET.""")
    def __init__(self):
        super(HttpGetBuiltin, self).__init__('http-get',
                                             output=HTTPResponse,
                                             input=None,
                                             singlevalue=True,                                             
                                             argspec=(ArgSpec('host'), ArgSpec('path', opt=True)))

    def execute(self, context, args, options=[]):       
        if len(args) == 1:
            host = args[0]
            path = '/'
        elif len(args) == 2:
            host = args[0]
            path = args[1]
        else:
            assert False         
        conn = httplib.HTTPConnection(host)
        conn.request('GET', path)
        response = conn.getresponse() 
        return response
BuiltinRegistry.getInstance().register_hotwire(HttpGetBuiltin())
