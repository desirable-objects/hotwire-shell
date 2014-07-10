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

import sys, logging, logging.config, StringIO

def log_except(logger=None, text=''):
    def annotate(func):
        def _exec_cb(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except:
                log_target = logger or logging
                log_target.exception('Exception in callback%s', text and (': '+text) or '')
        return _exec_cb
    return annotate

def init(default_level, debug_modules, prefix=None):
    rootlog = logging.getLogger() 
    fmt = logging.Formatter("%(asctime)s [%(thread)d] %(name)s %(levelname)s %(message)s",
                            "%H:%M:%S")
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)
    
    rootlog.setLevel(default_level)
    rootlog.addHandler(stderr_handler)
    for logger in [logging.getLogger(prefix+x) for x in debug_modules]:
        logger.setLevel(logging.DEBUG)

    logging.debug("Initialized logging")
