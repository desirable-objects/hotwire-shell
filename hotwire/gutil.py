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

from hotwire.sysdep import is_jython

if is_jython():
    from mainloop_null import *
else:
    from mainloop_g import *

def call_idle_once(func, *args, **kwargs):
    def func_false():
        func(*args, **kwargs)
        return False
    return call_idle(func_false)

def call_idle(func, *args, **kwargs):
    return call_timeout(0, func, *args, **kwargs)

_global_call_once_funcs = {}
def _run_removing_from_call_once(f):
    try:
        f()
    finally:
        del _global_call_once_funcs[f]
    
def call_timeout_once(timeout, func, **kwargs):
    """Call given func exactly once in the next idle time; if func is already pending,
    it will not be queued multiple times."""

    if func in _global_call_once_funcs:
        return
    id = call_timeout(timeout, _run_removing_from_call_once, func, **kwargs)
    _global_call_once_funcs[func] = id
    return id
    
def call_idle_once(func, **kwargs):
    return call_timeout_once(0, func, **kwargs)

def defer_idle_func(timeout=100, **kwargs):
    def wrapped(f):
        return lambda *margs: call_timeout_once(timeout, lambda: f(*margs), **kwargs)
    return wrapped
