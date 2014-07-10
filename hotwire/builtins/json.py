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

import os,sys,pickle,inspect,locale
from StringIO import StringIO

from hotwire.fs import FilePath

from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema

import simplejson

class LossyObjectJSONDumper(simplejson.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super(LossyObjectJSONDumper, self).__init__(*args, **kwargs)
        
    def default(self, o):
        name_repr = {}
        for name,member in sorted(inspect.getmembers(o), lambda a,b: locale.strcoll(a[0],b[0])):
            if name.startswith('_'):
                continue
            name_repr[name] = str(type(member))
        return self.encode(name_repr)

class JsonBuiltin(Builtin):
    __doc__ = _("""Convert object stream to JSON.""")
    def __init__(self):
        super(JsonBuiltin, self).__init__('json',
                                          output=str, # 'any'
                                          input=InputStreamSchema('any'),
                                          idempotent=True,
                                          argspec=None)

    def execute(self, context, args, options=[]):
        out = StringIO()
        for o in context.input:
            simplejson.dump(o, out, indent=2, cls=LossyObjectJSONDumper)
        # Should support binary streaming            
        for line in StringIO(out.getvalue()):
            if line.endswith('\n'):
                yield line[0:-1]
            else:
                yield line
BuiltinRegistry.getInstance().register_hotwire(JsonBuiltin())
