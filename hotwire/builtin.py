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

import os,sys,imp,logging,inspect

import hotwire
from hotwire.externals.singletonmixin import Singleton

_logger = logging.getLogger("hotwire.Builtin")

class ObjectStreamSchema(object):
    def __init__(self, otype, name=None, opt_formats=[]):
        self.otype = otype
        self.name = name
        self.opt_formats = opt_formats

class InputStreamSchema(ObjectStreamSchema):
    def __init__(self, otype, optional=False, **kwargs):
        super(InputStreamSchema, self).__init__(otype, **kwargs)
        self.optional = optional

class OutputStreamSchema(ObjectStreamSchema):
    def __init__(self, otype, merge_default=False, typefunc=None, **kwargs):
        super(OutputStreamSchema, self).__init__(otype, **kwargs)
        self.merge_default = merge_default
        self.typefunc = typefunc

class ArgSpec(object):
    __slots__ = ['name', 'opt']
    def __init__(self, name, opt=False):
        self.name = name
        self.opt = opt
        
class MultiArgSpec(object):
    """Specifies an unlimited number of similar arguments, with optional minimum."""
    __slots__ = ['name', 'min']
    def __init__(self, name, min=0):
        self.name = name
        self.min = min

class Builtin(object):
    name = property(lambda self: self._name)
    input = property(lambda self: self._input)
    input_type = property(lambda self: self._input and self._input.otype)
    input_is_optional = property(lambda self: self._input and self._input.optional)
    input_opt_formats = property(lambda self: self._input and self._input.opt_formats)
    output = property(lambda self: self._output)
    output_type = property(lambda self: self._output and self._output.otype or None)
    output_typefunc = property(lambda self: self._output and self._output.typefunc or None)
    output_opt_formats = property(lambda self: self._output and self._output.opt_formats or [])
    options = property(lambda self: self._options)
    options_passthrough = property(lambda self: self._options_passthrough, doc="""Treat all options as arguments.""")
    argspec = property(lambda self: self._argspec)
    aliases = property(lambda self: self._aliases)
    idempotent = property(lambda self: self._idempotent)
    undoable = property(lambda self: self._undoable)
    hasstatus = property(lambda self: self._hasstatus)
    hasmeta = property(lambda self: self._hasmeta)
    nodisplay = property(lambda self: self._nodisplay)
    threaded = property(lambda self: self._threaded)
    locality = property(lambda self: self._locality)
    api_version = property(lambda self: self._api_version)
    singlevalue = property(lambda self: self._singlevalue)
    doc = property(lambda self: self._doc)
    execfunc = property(lambda self: self._execfunc)
    flattened_args = property(lambda self: self._flattened_args)
    def __init__(self, name, 
                 input=None,
                 output=None,
                 options=[],
                 options_passthrough=False,
                 argspec=False,
                 aliases=[],
                 idempotent=False,
                 undoable=False,
                 hasstatus=False,
                 hasmeta=False,
                 nodisplay=False,
                 threaded=True,
                 locality='local',
                 doc=None,
                 api_version=0,
                 singlevalue=False):
        self._input=input
        self._output = isinstance(output, OutputStreamSchema) and output or OutputStreamSchema(output)
        self._options = options
        self._options_passthrough = options_passthrough
        if isinstance(argspec, tuple):
            self._argspec = tuple([isinstance(a, ArgSpec) and a or ArgSpec(a) for a in argspec])
        else:
            self._argspec = argspec
        self._name = name
        self._aliases = aliases 
        self._idempotent = idempotent
        self._undoable = undoable
        self._hasstatus = hasstatus
        self._hasmeta = hasstatus or hasmeta
        self._nodisplay = nodisplay
        self._threaded = threaded
        self._locality = locality
        self._api_version = api_version
        self._singlevalue = singlevalue
        if doc:
            self._doc = doc
        else:
            self._doc = inspect.getdoc(self)
        if hasattr(self, 'execute'):
            self._execfunc = self.execute
            self._flattened_args = False
        else:
            self._execfunc = self # Assume we implement __call_
            self._flattened_args = True

    def get_completer(self, *args, **kwargs):
        return None

    def cancel(self, context):
        pass

    def cleanup(self, context):
        pass

class BuiltinRegistry(Singleton):
    """Manages the set of registered builtins.
Currently there are 3 possible categories of builtin:
 "system" - These builtins are part of extensions shipped with the operating system.
 "hotwire" - Builtins included with the Hotwire source distribution
 "user" - Custom builtins loaded from per-user configuration.
"""    
    
    system_set = property(lambda self: self.__system_builtins, doc="""Set of system builtins""")
    hotwire_set = property(lambda self: self.__hotwire_builtins, doc="""Set of system builtins""")
    user_set = property(lambda self: self.__user_builtins, doc="""Set of user builtins""")

    def __init__(self):
        self.__system_builtins = set()        
        self.__hotwire_builtins = set()
        self.__user_builtins = set()
        self.__sets = [self.__user_builtins, self.__hotwire_builtins, self.__system_builtins]

    def __lookup_builtin(self, bset, name):
        for b in bset:
            if b.name == name or name in b.aliases:
                return b
        return None
    
    def __getitem__(self, name):
        for bset in self.__sets:
            b = self.__lookup_builtin(bset, name)
            if b: 
                return b
        raise KeyError(name)
        
    def __iter__(self):
        for bset in self.__sets:
            for b in bset:
                yield b   

    def __register(self, bset, builtin):
        existing = None
        for b in bset:
            if b.name == builtin.name:
                existing = b
                break
            b_aliases = set(b.aliases)
            builtin_aliases = set(builtin.aliases)
            inter = b_aliases.intersection(builtin_aliases)
            if len(inter) > 0:
                existing = b
                break
        if existing is not None:
            _logger.debug("deregistering existing instance %r", existing)
            bset.remove(existing)
        _logger.debug("registering %r (set: %r)", builtin, bset)
        bset.add(builtin)

    def register_system(self, builtin):
        self.__register(self.__system_builtins, builtin)
        
    def register_hotwire(self, builtin):
        self.__register(self.__hotwire_builtins, builtin)
        
    def register_user(self, builtin):
        self.__register(self.__user_builtins, builtin)                     

def _default_funcname_transform(name):
    return name.replace('_', '-')

class PyFuncBuiltin(Builtin):
    def __init__(self, func, name=None, **kwargs):
        name = func.func_name
        if not name:
            raise ValueError("Couldn't determine name of function: %s" % (f,))
        name = _default_funcname_transform(name)
        self.__func = func
        self.__func_args = inspect.getargspec(func)
        # 0x20 appears to signify the function is a generator according to the CPython sources
        self.__func_is_generator = func.func_code.co_flags & 0x20
        if not self.__func_is_generator:
            kwargs['singlevalue'] = True
        kwargs['output'] = 'any'
        kwargs['doc'] = inspect.getdoc(func)
        if self.__func_args[1] is not None:
            kwargs['argspec'] = MultiArgSpec(self.__func_args[1])
        else:
            kwargs['argspec'] = tuple(self.__func_args[0][1:])
        super(PyFuncBuiltin, self).__init__(name, **kwargs)
        self._execfunc = self.__func
    
def _builtin(registerfunc, **kwargs):
    def builtin_wrapper(f):
        builtin = PyFuncBuiltin(f, **kwargs)
        registerfunc(builtin)
        return f
    return builtin_wrapper

def builtin_user(**kwargs):
    return _builtin(BuiltinRegistry.getInstance().register_user, **kwargs)

def builtin_hotwire(**kwargs):   
    return _builtin(BuiltinRegistry.getInstance().register_hotwire, **kwargs)

def load():
    import hotwire.builtins.apply    
    import hotwire.builtins.cat
    import hotwire.builtins.cd
    import hotwire.builtins.cp
    import hotwire.builtins.current
    import hotwire.builtins.exit
    import hotwire.builtins.filter
    import hotwire.builtins.fsearch
    import hotwire.builtins.head    
    import hotwire.builtins.help
    import hotwire.builtins.history
    try:
        import simplejson
        have_simplejson = True
    except ImportError, e:
        have_simplejson = False
    if have_simplejson:
        import hotwire.builtins.json
    import hotwire.builtins.httpget
    import hotwire.builtins.kill
    import hotwire.builtins.iter
    import hotwire.builtins.ls
    import hotwire.builtins.mkdir
    import hotwire.builtins.mv
    import hotwire.builtins.open
    import hotwire.builtins.path
    import hotwire.builtins.pprint_builtin
    import hotwire.builtins.prop
    import hotwire.builtins.proc
    import hotwire.builtins.pyeval
    import hotwire.builtins.pyfilter
    import hotwire.builtins.pymap
    import hotwire.builtins.replace    
    import hotwire.builtins.rm
    import hotwire.builtins.newline    
    import hotwire.builtins.sechash
    import hotwire.builtins.selection    
    import hotwire.builtins.setenv
    import hotwire.builtins.sort
    import hotwire.builtins.stringify    
    import hotwire.builtins.sys_builtin    
    import hotwire.builtins.term
    import hotwire.builtins.uniq
    import hotwire.builtins.walk    
    import hotwire.builtins.write
