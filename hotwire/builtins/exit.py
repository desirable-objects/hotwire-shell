# This file is part of the Hotwire Shell project API.

# Copyright (C) 2008 Shixin Zeng <zeng.shixin@gmail.com>

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

from hotwire.builtin import Builtin, BuiltinRegistry

class ExitBuiltin(Builtin):
    __doc__ = _("""Close the current tab.""")
    def __init__(self):
        super(ExitBuiltin, self).__init__('exit', 
                                          argspec=None, 
                                          threaded=False)

    def execute(self, context, args):
        context.hotwire.get_ui().get_action('/Menubar/FileMenu/Close').activate()
        return []
    
BuiltinRegistry.getInstance().register_hotwire(ExitBuiltin())
