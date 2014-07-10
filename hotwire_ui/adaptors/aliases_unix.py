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

import os,sys

from hotwire.cmdalias import AliasRegistry

default_aliases = {'su': 'term su',                   
                   'vi': 'term vi',
                   'vim': 'term vim',
                   'gdb': 'term gdb',                   
                   'man': 'term man',
                   'info': 'term info',
                   'most': 'term most',                   
                   'less': 'term less',
                   'more': 'term more',
                   'ipython': 'term ipython',                     
                   'top': 'term top',
                   'iotop': 'term iotop',
                   'htop': 'term htop',                     
                   'powertop': 'term powertop',                   
                   'nano': 'term nano',
                   'pico': 'term pico',
                   'irssi': 'term irssi',
                   'mutt': 'term mutt',
                   'nethack': 'term nethack',
                  }
aliases = AliasRegistry.getInstance()
for name,value in default_aliases.iteritems():
    aliases.insert(name, value)
