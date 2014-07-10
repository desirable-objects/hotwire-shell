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

import os, sys, threading, Queue, logging, string, re, time, traceback
import posixpath, locale
from StringIO import StringIO

import hotwire.fs
from hotwire.fs import path_normalize, unix_basename, FilePath, open_text_file
from hotwire.sysdep.fs import Filesystem, File
from hotwire.async import IterableQueue, MiniThreadPool
from hotwire.builtin import BuiltinRegistry, Builtin, ArgSpec, MultiArgSpec
import hotwire.util
from hotwire.util import quote_arg, assert_strings_equal, class_is_assignable
from hotwire.gutil import call_idle,call_timeout
import hotwire.script
import hotwire.externals.shlex as shlex
from hotwire.externals.singletonmixin import Singleton
from hotwire.externals.dispatch import dispatcher

_logger = logging.getLogger("hotwire.Command")

class PipelineTypeData(object):
    """Represents a snapshot of metadata from a pipeline execution."""
    type = property(lambda self: self._type)
    single = property(lambda self: self._single)
    __slots__ = ['_type', '_single']
    def __init__(self, pipeline):
        super(PipelineTypeData, self).__init__()
        self._type = pipeline.get_output_type()
        self._single = pipeline.is_singlevalue

class HotwireContext(object):
    cwd = property(lambda self: self.get_cwd(), doc="""Current working directory for this context.""")
    
    """The interface to manipulating a Hotwire execution shell.  Item
    such as the current working diretory may be changed via this class,
    and subclasses define further extended commands."""
    def __init__(self, initcwd=None):
        super(HotwireContext, self).__init__()
        self.chdir(initcwd or os.path.expanduser('~'))
        _logger.debug("Context created, dir=%s" % (self.get_cwd(),))

    def chdir(self, dpath):
        if not isinstance(dpath, unicode):
            dpath = unicode(dpath, 'utf-8')
        dpath = os.path.expanduser(dpath)
        newcwd = os.path.isabs(dpath) and dpath or posixpath.join(self.__cwd, dpath)
        newcwd = path_normalize(newcwd)
        _logger.debug("chdir: %s    post-normalize: %s", dpath, newcwd)
        os.stat(newcwd) # lose on nonexistent
        self.__cwd = newcwd
        dispatcher.send('cwd', self, newcwd)
        return self.__cwd

    def get_cwd(self):
        return self.__cwd
    
    def get_gtk_event_time(self):
        return 0

    def info_msg(self, msg):
        _logger.info("msg: %s", msg)
    
    def get_current_output_metadata(self):
        raise NotImplementedError()
    
    def get_current_output_ref(self):
        raise NotImplementedError()
    
    def snapshot_output(self, ref):
        raise NotImplementedError()
    
    def snapshot_selected_output(self, ref):
        raise NotImplementedError()

class CommandContext(object):
    """An execution snapshot for a Command.  Holds the working directory
    when the command started, the input stream, and allows accessing
    the execution context."""
    def __init__(self, hotwire):
        self.input = None
        self.input_type = None
        self.input_is_first = False
        self.pipeline = None
        self.cwd = hotwire.get_cwd()
        self.gtk_event_time = hotwire.get_gtk_event_time()
        try:
            self.current_output_metadata = hotwire.get_current_output_metadata()
            self.current_output_ref = hotwire.get_current_output_ref()
            _logger.debug("got current metadata %r, ref: %r", self.current_output_metadata,
                          self.current_output_ref)
        except NotImplementedError, e:
            _logger.debug("no current output!")
            self.current_output_metadata = None
            self.current_output_ref = None
        self.hotwire = hotwire
        self.__auxstreams = {}
        self.__metadata_handler = None
        # Private attributes to be used by the builtin
        self.attribs = {}
        self.options = []
        self.cancelled = False
        
    def snapshot_current_output(self, selected=False):
        if self.current_output_ref is None:
            return None
        if selected:
            return self.hotwire.snapshot_selected_output(self.current_output_ref)
        else:
            return self.hotwire.snapshot_output(self.current_output_ref)

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline

    def attach_auxstream(self, auxstream):
        self.__auxstreams[auxstream.name] = auxstream

    def auxstream_append(self, name, obj):
        self.__auxstreams[name].queue.put(obj)

    def auxstream_complete(self, name):
        self.auxstream_append(name, None)

    def get_auxstreams(self):
        for obj in self.__auxstreams.itervalues():
            yield obj

    def push_undo(self, fn):
        self.pipeline.push_undo(fn)

    def set_metadata_handler(self, fn):
        self.__metadata_handler = fn

    def status_notify(self, status, progress=-1):
        self.metadata('hotwire.status', 0, (status, progress))
            
    def metadata(self, metatype, flags, value):
        if self.__metadata_handler:
            self.__metadata_handler(metatype, flags, value)

class CommandQueue(IterableQueue):
    def __init__(self):
        IterableQueue.__init__(self)
        self.opt_type = None

    def negotiate(self, out_fmts, in_fmts):
        _logger.debug("negotiating stream; out_fmts: %s in_fmts: %s", out_fmts, in_fmts)
        for fmt in out_fmts:
            if fmt in in_fmts:
                self.opt_type = fmt
                _logger.debug("negotiated optimized type %s", fmt)
                break
            
    def cancel(self):
        self.put(None)
        
class CommandFileQueue(object):
    """Implements command queue protocol, yielding lines from a file."""
    def __init__(self, f):
        self.__f = f
        
    def negotiate(self, out_fmts, in_fmts):
        pass
        
    def __iter__(self):
        for line in self.__f:
            yield line
        self.__f.close()
        self.__f = None
        
    def cancel(self):
        if self.__f is None:
            return
        self.__f.close()
        self.__f = None

class CommandAuxStream(object):
    def __init__(self, command, schema):
        self.command = command
        self.name = schema.name
        self.schema = schema
        self.queue = CommandQueue()

class CommandException(Exception):
    pass

class CommandArgument(unicode):
    """An argument for a command, with the additional metadata of quotation status."""
    def __new__(cls, value, quoted=False):
        inst = super(CommandArgument, cls).__new__(cls, value)
        inst.isquoted = quoted
        return inst

class Command(object):
    """Represents a complete executable object in a pipeline."""

    def __init__(self, builtin, args, options, hotwire, tokens=None, in_redir=None, out_redir=None, 
                  out_append=False):
        super(Command, self).__init__()
        self.builtin = builtin
        self.context = CommandContext(hotwire)
        # The concept of multiple object streams is dead. 
        #for schema in self.builtin.get_aux_outputs():
        #    self.context.attach_auxstream(CommandAuxStream(self, schema))
        if self.builtin.hasmeta:
            def on_meta(*args):
                dispatcher.send('metadata', self, *args)
            self.context.set_metadata_handler(on_meta)
        self.input = None
        self.output = CommandQueue()
        self.map_fn = lambda x: x
        self.args = args
        self.context.options = options
        self.in_redir = in_redir and FilePath(os.path.expanduser(in_redir), self.context.cwd)
        self.out_redir = out_redir and FilePath(os.path.expanduser(out_redir), self.context.cwd)
        self.out_append = out_append
        
        self.__thread = None
        self.__executing_sync = None
        self._cancelled = False
        self.__tokens = tokens

    def set_pipeline(self, pipeline):
        self.context.set_pipeline(pipeline)

    def set_input(self, input, is_first=False):
        self.input = input       
        self.context.input = self.input
        self.context.input_is_first = is_first
        
    def set_input_type(self, in_type):
        """Note the pipeline object type used for input."""
        self.context.input_type = in_type
        
    def disconnect(self):
        self.context = None
        
    def cancel(self):
        if self._cancelled:
            return
        self._cancelled = True
        self.context.cancelled = True
        if self.context.input:
            self.context.input.cancel()
        self.builtin.cancel(self.context)

    def get_input_opt_formats(self):
        return self.builtin.input_opt_formats

    def get_output_opt_formats(self):
        return self.builtin.output_opt_formats

    def execute(self, force_sync, **kwargs):
        if force_sync or not self.builtin.threaded:
            _logger.debug("executing sync: %s", self)
            self.__executing_sync = True
            self.__run(**kwargs)
        else:         
            _logger.debug("executing async: %s", self)              
            self.__executing_sync = False             
            self.__thread = threading.Thread(target=self.__run)
            self.__thread.setDaemon(True)            
            self.__thread.start()

    def set_output_queue(self, queue, map_fn):
        self.output = queue
        self.map_fn = map_fn

    def get_auxstreams(self):
        for obj in self.context.get_auxstreams():
            yield obj
    
    def get_tokens(self):
        return self.__tokens

    def __run(self, *args, **kwargs):
        if self._cancelled:
            _logger.debug("%s cancelled, returning", self)
            self.output.put(self.map_fn(None))
            return
        try:
            matched_files = []
            oldlen = 0
            for globarg_in in self.args:
                if isinstance(globarg_in, CommandArgument) and globarg_in.isquoted:
                    globarg = globarg_in
                    newlen = oldlen                    
                else:
                    globarg = os.path.expanduser(globarg_in)
                    matched_files.extend(hotwire.fs.dirglob(self.context.cwd, globarg))
                    _logger.debug("glob on %s matched is: %s", globarg_in, matched_files) 
                    newlen = len(matched_files)
                if oldlen == newlen:
                    matched_files.append(globarg)
                    newlen += 1
                oldlen = newlen
            target_args = [matched_files]
            _logger.info("Execute '%s' args: %s options: %s", self.builtin, target_args, self.context.options)
            kwargs = {}
            if self.context.options and not self.builtin.flattened_args:
                kwargs['options'] = self.context.options
            if self.input is not None and self.input.opt_type and not self.in_redir:
                kwargs['in_opt_format'] = self.input.opt_type                
            if self.output.opt_type and not self.out_redir:
                kwargs['out_opt_format'] = self.output.opt_type
            if self.in_redir:
                _logger.debug("input redirected, opening %s", self.in_redir)
                self.context.input = CommandFileQueue(open_text_file(self.in_redir, 'r'))
            if self.out_redir:
                _logger.debug("output redirected, opening %s", self.out_redir)
                outfile = open_text_file(self.out_redir, self.out_append and 'a+' or 'w')
            else:
                outfile = None
            try:
                exectarget = self.builtin.execfunc
                if self.builtin.flattened_args:
                    target_args = target_args[0]
                execresult = exectarget(self.context, *target_args, **kwargs)                
                if self.builtin.singlevalue:
                    if outfile:
                        outfile.write(unicode(execresult))
                    else:
                        self.output.put(execresult)
                else:
                    for result in execresult:
                        # if it has status, let it do its own cleanup
                        if self._cancelled and not self.builtin.hasstatus:
                            _logger.debug("%s cancelled, returning", self)
                            self.output.put(self.map_fn(None))
                            dispatcher.send('complete', self)
                            return
                        if outfile and (result is not None):
                            result = unicode(result)
                            outfile.write(result)
                        else:                        
                            self.output.put(self.map_fn(result))
            finally:
                if outfile:
                    outfile.close()
                self.builtin.cleanup(self.context)
        except Exception, e:
            _logger.debug("Caught exception from command: %s", e, exc_info=True)
            if self.__executing_sync:
                raise
            else:
                dispatcher.send('exception', self, e)
        self.output.put(self.map_fn(None))
        dispatcher.send('complete', self)
        
    def get_executing_sync(self):
        return self.__executing_sync      

    def __str__(self):
        def unijoin(args):
            return ' '.join(map(unicode, args))
        args = [self.builtin.name]
        args.extend(self.context.options)
        for cmdarg in self.args:
            if isinstance(cmdarg, CommandArgument) and cmdarg.isquoted:
                args.append(quote_arg(cmdarg))                
            else:
                args.append(cmdarg)
        if self.in_redir:
            args.extend(['<', self.in_redir])
        if self.out_redir:
            args.extend(['>', self.out_redir])            
        return unijoin(args)

class PipelineParseException(Exception):
    pass

class ParsedToken(object):
    def __init__(self, text, start, end=None, was_unquoted=False, quoted=False):
        self.text = text 
        self.start = start
        self.end = end or (start + len(text))
        self.was_unquoted = was_unquoted
        self.quoted = quoted

    def __repr__(self):
        return 'Token(%s %d %d %s)' % (self.text, self.start, self.end, self.quoted)

class ParsedVerb(ParsedToken):
    def __init__(self, verb, start, builtin=None, **kwargs):
        super(ParsedVerb, self).__init__(verb, start, **kwargs)
        self.resolved = not not builtin 
        self.builtin = builtin

    def resolve(self, resolution):
        self.resolved = True
        self.builtin = None #FIXME or delete

class CountingStream(object):
    def __init__(self, stream):
        super(CountingStream, self).__init__()
        self.__stream = stream
        self.__offset = 0
        self.__at_eof = False

    def read(self, c):
        result = self.__stream.read(c)
        resultlen = len(result)
        self.__offset += resultlen
        self.__at_eof = resultlen < c
        return result

    def at_eof(self):
        return self.__at_eof

    def get_count(self):
        return self.__offset

class BaseCommandResolver(object):
    """Expands command names.  Example: ifconfig => sys ifconfig"""
    def __init__(self):
        super(BaseCommandResolver, self).__init__()
        # TODO move this logic elsewhere somehow better; maybe stick in hotwire_ui/pipeline.py.
        from hotwire.completion import VerbCompleter
        self.__verb_completer = VerbCompleter()
        
    def resolve(self, text, context):
        resolutions = []
        vc = self.__verb_completer
            
        resolution_match = None
        for completion in vc.completions(text, context.get_cwd()):
            target = completion.target
            if self._resolve_verb_completion(text, completion):
                resolution_match = completion
                break
        _logger.debug("resolution match is %s", resolution_match)                
        if resolution_match:            
            return self._expand_verb_completion(resolution_match)
        return (None, None)
    
    def _resolve_verb_completion(self, text, completion):
        fs = Filesystem.getInstance()
        target = completion.target
        if not (isinstance(target, File) and not target.is_directory):
            return False
        # Determine whether this input matches an executable file
        return fs.path_executable_match(text, target.path)
    
    def _expand_verb_completion(self, completion):
        target = completion.target
        if isinstance(target, File):
            return (BuiltinRegistry.getInstance()['sys'], [target.path])       

class Pipeline(object):
    """A sequence of Commands."""
    
    is_singlevalue = property(lambda self: self._is_singlevalue)

    __ws_re = re.compile(r'\s+')

    def __init__(self, components, input_type='unknown', input_optional=False,
                 output_type='unknown', locality=None,
                 idempotent=False,
                 undoable=False,
                 singlevalue=False):
        super(Pipeline, self).__init__()
        self.__executing_sync = False
        self.__components = components
        for component in self.__components:
            component.set_pipeline(self)
        self.__locality = locality
        self.__input_type = input_type
        self.__input_optional = input_optional
        self.__idempotent = idempotent
        self.__undoable = undoable
        self._is_singlevalue = singlevalue
        self.__output_type = output_type
        self.__undo = []
        self.__cmd_metadata_lock = threading.Lock()
        self.__idle_emit_cmd_metadata_id = 0
        self.__cmd_metaidx = {} # cmd -> int
        self.__cmd_metadata = {}
        self.__cmd_complete_count = 0
        self.__state = 'waiting'
        self.__completion_time = None
        
    def get_state(self):
        return self.__state     

    def disconnect(self):
        for cmd in self.__components:
            cmd.disconnect()
    
    def __execute_internal(self, force_sync, opt_formats=[], assert_all_threaded=False):
        _logger.debug("Executing %s", self)
        self.__set_state('executing')
        meta_idx = 0          
        for i,cmd in enumerate(self.__components):
            if assert_all_threaded and not cmd.builtin.threaded:
                raise ValueError("assert_all_threaded is enabled but trying to execute non-threaded builtin %s" % (cmd.builtin,))
            dispatcher.connect(self.__on_cmd_complete, 'complete', cmd)
            dispatcher.connect(self.__on_cmd_exception, "exception", cmd)
            # Here we record which commands include metadata, and
            # pass in the index in the pipeline for them.
            if cmd.builtin.hasmeta:
                _logger.debug("connecting to metadata on cmd %s, idx=%s", cmd, meta_idx)
                dispatcher.connect(self.__on_cmd_metadata, 'metadata', cmd)
                self.__cmd_metaidx[cmd] = meta_idx
                meta_idx += 1                
        prev_opt_formats = []
        for cmd in self.__components:
            if cmd.input:
                cmd.input.negotiate(prev_opt_formats, cmd.get_input_opt_formats())
            prev_opt_formats = cmd.get_output_opt_formats()
            if cmd.out_redir:
                prev_opt_formats = []
        last = self.__components[-1]
        if not last.out_redir:
            last_opt_fmts = last.get_output_opt_formats()
        else:
            last_opt_fmts = []
        last.output.negotiate(last_opt_fmts, opt_formats)
        for i,cmd in enumerate(self.__components[:-1]):
            cmd.execute(force_sync)
        last.execute(force_sync)
        
    def validate_state_transition(self, state):
        if self.__state == 'waiting':
            return state in ('executing', 'exception')
        elif self.__state == 'executing':
            return state in ('complete', 'cancelled', 'exception')
        elif self.__state in ('cancelled', 'exception', 'undone'):
            return None
        elif self.__state == 'complete':
            return state in ('undone',) and self.get_undoable()
        assert(False)
        
    def is_complete(self):
        return self.__state in ('complete', 'cancelled', 'exception', 'undone')
        
    def __set_state(self, state):
        trans = self.validate_state_transition(state)
        if trans is None:
            _logger.debug("ignoring transition from state %s to %s", self.__state, state)
            return
        elif not trans:
            raise ValueError("Invalid state transition %s to %s", self.__state, state)
        
        self.__state = state
        if self.is_complete():
            self.__completion_time = time.time()         
        dispatcher.send('state-changed', self)

    def execute(self, **kwargs):
        self.__execute_internal(False, **kwargs)

    def execute_sync(self, **kwargs):
        self.__executing_sync = True
        self.__execute_internal(True, **kwargs)

    def push_undo(self, fn):
        self.__undo.append(fn)

    def get_undoable(self):
        return self.__undoable

    def undo(self):
        for fn in self.__undo:
            fn()
        self.__set_state('undone')

    def get_completion_time(self):
        return self.__completion_time

    def get_idempotent(self):
        return self.__idempotent

    def get_status_commands(self):
        for cmd in self.__components:
            if cmd.builtin.hasstatus:
                yield cmd.builtin.name

    def __on_cmd_metadata(self, key, flags, meta, sender=None):
        cmd = sender
        cmdidx = self.__cmd_metaidx[cmd]
        self.__cmd_metadata_lock.acquire()
        if self.__idle_emit_cmd_metadata_id == 0:
            self.__idle_emit_cmd_metadata_id = call_timeout(200, self.__idle_emit_cmd_metadata)
        self.__cmd_metadata[(cmd, cmdidx, key)] = (flags, meta)
        self.__cmd_metadata_lock.release()

    def __idle_emit_cmd_metadata(self):
        _logger.debug("signalling command metadata")      
        self.__cmd_metadata_lock.acquire()
        self.__idle_emit_cmd_metadata_id = 0
        meta_ref = self.__cmd_metadata
        self.__cmd_metadata = {}
        self.__cmd_metadata_lock.release()
        for (cmd,cmdidx,key),(flags,meta) in meta_ref.iteritems():
            dispatcher.send('metadata', self, cmdidx, cmd, key, flags, meta)

    def __on_cmd_complete(self, sender=None):
        cmd = sender
        _logger.debug("command complete: %s", cmd)
        if cmd.get_executing_sync():
            self.__idle_handle_cmd_complete(cmd)
        else:  
            call_idle(lambda: self.__idle_handle_cmd_complete(cmd))
        
    def __idle_handle_cmd_complete(self, cmd):
        self.__cmd_complete_count += 1
        if self.__cmd_complete_count == len(self.__components):
            self.__set_state('complete')

    def __on_cmd_exception(self, e, sender=None):
        cmd = sender
        if not self.__state == 'executing':
            return        
        try:
            self.cancel(changestate=False)
        except:
            _logger.exception("Nested exception while cancelling")
            pass
        dispatcher.send('exception', self, e, cmd)
        self.__exception_info = (e.__class__, str(e), cmd, traceback.format_exc())
        self.__set_state('exception')
        
    def get_exception_info(self):
        return self.__exception_info

    def get_output(self):
        return self.__components[-1].output

    def get_input_type(self):
        return self.__input_type

    def get_input_optional(self):
        return self.__input_optional

    def get_output_type(self):
        return self.__output_type
    
    def get_output_metadata(self):
        return PipelineTypeData(self)

    def get_auxstreams(self):
        for cmd in self.__components:
            for obj in cmd.get_auxstreams():
                yield obj

    def cancel(self, changestate=True):
        if not self.__state == 'executing':
            return
        if changestate:
            self.__set_state('cancelled')        
        for component in self.__components:
            component.cancel()        

    def is_nodisplay(self):
        return self.__components[0].builtin.nodisplay

    def set_output_queue(self, queue, map_fn):
        self.__components[-1].set_output_queue(queue, map_fn)
        
    def set_input_queue(self, queue):
        # FIXME - remove this is_first bit
        self.__components[0].set_input(queue, is_first=True)

    def get_locality(self):
        return self.__locality

    @staticmethod
    def streamtype_is_assignable(out_spec, in_spec, in_optional):
        if out_spec is None:
            return in_optional
        if in_spec in ('any', 'identity'):
            return True
        if out_spec == 'any':
            # Allow anys to connect to anything...even though it may TypeError
            return True
        if out_spec is in_spec:
            return True
        return class_is_assignable(in_spec, out_spec)

    @staticmethod
    def __parse_option_or_arg(opts, arg, raise_on_invalid=True):
        """If argument string is an option, parse it into components and canonicalize it.
Otherwise, return arg."""
        if arg.startswith('--'):
            args = [arg[1:]] # we re-add the '-' below
        elif arg.startswith('-') and len(arg) >= 2:
            args = list(arg[1:])
        else:
            return False
        results = []
        for arg in args:
            found = False
            if opts is not None:
                for aliases in opts:
                    if '-'+arg in aliases:
                        results.append(aliases[0])
                        found = True
                        break
            if (not found) and raise_on_invalid:                
                    raise PipelineParseException("Invalid option %s" % (arg,))
        return results

    @staticmethod
    def mkparser(text):
        if isinstance(text, unicode):
            utext = text
        else:
            utext = unicode(text, 'utf-8')
        countstream = CountingStream(StringIO(utext))
        parser = shlex.shlex(countstream, posix=True)
        parser.wordchars += ',./[]{}~!@$%^&*()-_=+:;'
        return (countstream, parser)

    @staticmethod
    def tokenize(text, context=None, assertfn=None, accept_partial=False, internal=False):
        result = []
        _logger.debug("parsing '%s'", text)
        
        (countstream, parser) = Pipeline.mkparser(text)
        
        def mktoken(text, *args, **kwargs):
            if internal:
                return ParsedToken(text, -1, **kwargs)
            return ParsedToken(text, *args, **kwargs)
        
        is_initial = True
        first_token = None
        curpos = 0
        while True:
            try:
                (token, quoted) = parser.get_token_info()
            except ValueError, e:
                # FIXME gross, but...any way to fix?
                msg = hasattr(e, 'message') and e.message or (e.args[0])
                was_quotation_error = (e.message == 'No closing quotation' and parser.token[0:1] == "'")
                if (not accept_partial) or (not was_quotation_error):
                    _logger.debug("caught lexing exception", exc_info=True)
                    raise PipelineParseException(e)
                arg = parser.token[1:]
                if arg:
                    token = mktoken(arg, curpos+1, was_unquoted=True)
                    _logger.debug("handling unclosed quote, returning %s", token)
                    yield token
                    return
                else:
                    _logger.debug("handling unclosed quote, but token was empty")
                    return
            _logger.debug("tokenize: %r", token)
            # empty input
            if token is None:
                break 
            is_initial = False
            end = countstream.get_count()
            if not quoted and token in ('|', '<', '>', '>>'):
                if token == '|':
                    yield hotwire.script.PIPE
                elif token == '>':
                    yield hotwire.script.REDIR_OUT
                elif token == '>>':
                    yield hotwire.script.REDIR_OUT_APPEND
                elif token == '<':
                    yield hotwire.script.REDIR_IN           
            else:
                if end-curpos > len(token):
                    end = curpos+len(token)
                yield mktoken(token, curpos, end=end, quoted=quoted)
            curpos = end
        
    @staticmethod
    def create(context, resolver, *tokens, **kwargs):
        if context is None:
            context = HotwireContext()
        accept_partial = (('accept_partial' in kwargs) and kwargs['accept_partial'])
        components = []
        undoable = None
        idempotent = True
        prev = None
        pipeline_input_type = 'unknown'
        pipeline_input_optional = 'unknown'
        pipeline_output_type = None
        prev_locality = None
        pipeline_singlevalue = None
        pipeline_type_validates = True
        pushback = []
        tokens = list(tokens)
        def pull_token():
            if pushback:
                return pushback.pop(0)
            else:
                return tokens.pop(0)            
        while tokens or pushback:
            builtin_token = pull_token()
            _logger.debug("token = %r", builtin_token)    
                
            def forcetoken(t):
                # Allow passing plain strings for convenience from Python.
                # Treat them as quoted.
                if isinstance(t, basestring):
                    return ParsedToken(t, -1, quoted=True)
                return t
            
            builtin_token = forcetoken(builtin_token)

            # Attempt to determine which builtin we're using
            if isinstance(builtin_token, Builtin):
                b = builtin_token
                cmdargs = []
            # If we're parsing without a resolver, assume we're using sys
            elif isinstance(builtin_token, ParsedToken):
                try:
                    b = BuiltinRegistry.getInstance()[builtin_token.text]
                    cmdargs = []
                except KeyError, e:
                    if resolver:
                        (b, cmdargs) = resolver.resolve(builtin_token.text, context)
                        _logger.debug("resolved: %r to %r %r", builtin_token.text, b, cmdargs)
                        if not b:
                            raise PipelineParseException(_('No matches for %s') % (builtin_token.text,))
                    else:
                        b = BuiltinRegistry.getInstance()['sys']
                        cmdargs = [ParsedToken(builtin_token.text, builtin_token.start, end=builtin_token.end)]
            elif builtin_token in (hotwire.script.PIPE, hotwire.script.REDIR_IN, hotwire.script.REDIR_OUT, hotwire.script.REDIR_OUT_APPEND):
                raise PipelineParseException(_("Unexpected token %d") % (builtin_token,))
            else:
                _logger.error("unknown in parse stream: %r", builtin_token)
                assert False
                
            _logger.debug("target builtin is %r", b)
                
            # We maintain the set of all tokens we processed in the command so that the completion system can use them.
            alltokens = [builtin_token]
            cmdargs = map(forcetoken, cmdargs)
            alltokens.extend(cmdargs)
                
            in_redir = None
            out_redir = None

            # Pull from the stream to get all the arguments
            while tokens:
                cmdarg = forcetoken(pull_token())
                if cmdarg == hotwire.script.PIPE:
                    break
                elif cmdarg == hotwire.script.REDIR_IN:
                    if not tokens:
                        raise PipelineParseException(_('Must specify target for input redirection'))
                    in_redir_token = pull_token()
                    in_redir = in_redir_token.text
                    alltokens.append(in_redir_token)
                elif cmdarg == hotwire.script.REDIR_OUT:
                    if not tokens:
                        raise PipelineParseException(_('Must specify target for output redirection'))                   
                    out_redir_token = pull_token()
                    out_redir = out_redir_token.text                     
                    alltokens.append(out_redir_token)               
                else:
                    alltokens.append(cmdarg)
                    cmdargs.append(cmdarg)         

            builtin_opts = b.options

            options = []
            expanded_cmdargs = []
            options_ended = False
            raise_on_invalid_options = not (b.options_passthrough or accept_partial)
            _logger.debug("raise: %r valid options %r, argument/option pool: %r", raise_on_invalid_options,
                          builtin_opts, cmdargs)
            for token in cmdargs:
                arg = CommandArgument(token.text, quoted=token.quoted)
                if token.text == u'--':
                    options_ended = True
                elif options_ended:
                    expanded_cmdargs.append(arg)
                else:      
                    argopts = Pipeline.__parse_option_or_arg(builtin_opts, token.text, 
                                                             raise_on_invalid=raise_on_invalid_options)
                    if argopts:
                        options.extend(argopts)
                    else:
                        expanded_cmdargs.append(arg)
                        
            argspec = b.argspec
            if argspec is False or accept_partial:
                # If we don't have an argspec, don't do any checking
                pass
            elif argspec is None:
                if len(expanded_cmdargs) > 0:
                    raise PipelineParseException(_('Command %s takes no arguments, %d given') % (b.name, len(expanded_cmdargs)))
            elif isinstance(argspec, MultiArgSpec):
                if len(expanded_cmdargs) < argspec.min:
                    raise PipelineParseException(_("Command %s requires %d args, %d given") % (b.name,
                                                                                               argspec.min,
                                                                                               len(expanded_cmdargs)))  
            elif isinstance(argspec, tuple):
                mincount = 0
                for o in argspec:
                    if not o.opt: 
                        mincount += 1
                if len(expanded_cmdargs) > len(argspec):
                    raise PipelineParseException(_("Command %s takes at most %d args, %d given") % (b.name,
                                                                                                    len(argspec),
                                                                                                    len(expanded_cmdargs)))
                if len(expanded_cmdargs) < mincount:
                    raise PipelineParseException(_("Command %s requires %d args, %d given") % (b.name,
                                                                                               mincount,
                                                                                               len(expanded_cmdargs)))                
            cmdtokens = [builtin_token]
            cmdtokens.extend(cmdargs)
            cmd = Command(b, expanded_cmdargs, options, context, tokens=alltokens, in_redir=in_redir, out_redir=out_redir)
            components.append(cmd)
            if (not in_redir) and prev:
                cmd.set_input(prev.output)
            if pipeline_output_type:
                cmd.set_input_type(pipeline_output_type)
            input_accepts_type = cmd.builtin.input_type
            input_optional = cmd.builtin.input_is_optional
            if pipeline_input_optional == 'unknown':
                pipeline_input_optional = input_optional
            _logger.debug("Validating input %s vs prev %s", input_accepts_type, pipeline_output_type)

            if prev and not pipeline_output_type:
                raise PipelineParseException(_("Command %s yields no output for pipe") % \
                                             (prev.builtin.name))
            if (not prev) and input_accepts_type and not (input_optional): 
                raise PipelineParseException(_("Command %s requires input of type %s") % \
                                             (cmd.builtin.name, input_accepts_type))
            if input_accepts_type and prev \
                   and not Pipeline.streamtype_is_assignable(pipeline_output_type, input_accepts_type, input_optional):
                raise PipelineParseException(_("Command %s yields '%s' but %s accepts '%s'") % \
                                             (prev.builtin.name, pipeline_output_type, cmd.builtin.name, input_accepts_type))
            if (not input_optional) and (not input_accepts_type) and pipeline_output_type:
                raise PipelineParseException(_("Command %s takes no input but type '%s' given") % \
                                             (cmd.builtin.name, pipeline_output_type))
            locality = cmd.builtin.locality
            if prev_locality and locality and (locality != prev_locality):
                raise PipelineParseException(_("Command %s locality conflict with '%s'") % \
                                             (cmd.builtin.name, prev.builtin.name))
            prev_locality = locality
                
            if out_redir:
                prev = None
            else:
                prev = cmd
            if pipeline_input_type == 'unknown':
                pipeline_input_type = input_accepts_type
                
            if pipeline_singlevalue is None or (pipeline_singlevalue):
                pipeline_singlevalue = cmd.builtin.singlevalue

            if cmd.builtin.output_type != 'identity':
                if context and cmd.builtin.output_typefunc:
                    pipeline_output_type = cmd.builtin.output_typefunc(context)
                    _logger.debug("retrieved type %r from typefunc", pipeline_output_type)
                else:
                    pipeline_output_type = cmd.builtin.output_type

            if undoable is None:
                undoable = cmd.builtin.undoable
            elif not cmd.builtin.undoable:
                undoable = False

            if not cmd.builtin.idempotent:
                idempotent = False
                
        if len(components) == 0:
            raise PipelineParseException(_("Empty pipeline"))

        if undoable is None:
            undoable = False
        pipeline = Pipeline(components,
                            input_type=pipeline_input_type,
                            input_optional=pipeline_input_optional,
                            output_type=pipeline_output_type,
                            locality=prev_locality,
                            undoable=undoable,
                            idempotent=idempotent,
                            singlevalue=pipeline_singlevalue)
        _logger.debug("Parsed pipeline %s (%d components, input %s, output %s)",
                      pipeline, len(components),
                      pipeline.get_input_type(),
                      pipeline.get_output_type())
        return pipeline 

    @staticmethod
    def parse(text, context=None, resolver=None, accept_partial=False):
        tokens = list(Pipeline.tokenize(text, context, accept_partial=accept_partial))
        return Pipeline.create(context, resolver, accept_partial=accept_partial, *tokens)
    
    def __iter__(self):
        for component in self.__components:
            yield component
        
    def __getitem__(self, i):
        return self.__components[i]

    def __str__(self):
        return string.join(map(lambda x: x.__str__(), self.__components), ' | ')        

class PipelineLanguage(object):
    """Abstract class representing a supported input language."""
    
    uuid = property(lambda self: self._uuid, doc="""UUID associated with this language, used for unambiguous identification""")
    prefix = property(lambda self: self._prefix, doc="""The syntax prefix typed by the user""")
    fileext = property(lambda self: self._fileext, doc="""File extension used to denote this language.""")
    langname = property(lambda self: self._langname, doc="""The human-readable name of the language (e.g. "Python")""")
    icon = property(lambda self: self._icon, doc="""Icon name for this language""")
    builtin_eval = property(lambda self: self._builtin_eval, doc="""The Hotwire Builtin object used for execution""")
    interpreter_exec = property(lambda self: self._interpreter_exec, doc="""The executable interpreter name (if required)""")
    exec_args = property(lambda self: self._exec_args, doc="""The interpreter arguments use for execution of a string""")
    script_content = property(lambda self: self._script_content, doc="""Default file content used for new scripts.""")
    script_content_line = property(lambda self: self._script_content_line, doc="""Default cursor line offset for script.""")    
    
    def __init__(self, uuid, prefix, fileext, langname, icon, 
                  builtin_eval=None, interpreter_exec=None, exec_args=None,
                  script_content=None, script_content_line=-1):
        super(PipelineLanguage, self).__init__()
        self._uuid = uuid
        self._prefix = prefix
        self._fileext = fileext
        self._langname = langname
        self._icon = icon
        self._builtin_eval = builtin_eval
        self._interpreter_exec = interpreter_exec
        self._exec_args = exec_args
        self._script_content = script_content
        self._script_content_line = script_content_line
    
    def get_completer(self, text):
        raise NotImplementedError()
    
class PipelineLanguageRegistry(Singleton):
    """Registry for supported pipeline languages."""
    def __init__(self):
        self.__langs = {} # uuid->lang
        
    def __getitem__(self, uuid):
        return self.__langs[uuid]
        
    def get_by_fileext(self, ext):
        for lang in self:
            if lang.fileext == ext:
                return lang
        
    def __iter__(self):
        for x in self.__langs.itervalues():
            yield x
            
    def iter_sorted(self):
        langs = list(self)
        # Append Hotwire and Python in order
        result = [self['62270c40-a94a-44dd-aaa0-689f882acf34'], self['da3343a0-8bce-46ed-a463-2d17ab09d9b4']]
        for lang in sorted(langs, lambda a,b: locale.strcoll(a.langname, b.langname)):
            if lang.builtin_eval is not None:
                continue
            result.append(lang)
        for lang in result:
            yield lang               

    def register(self, lang):
        if lang.uuid in self.__langs:
            raise ValueError("Language uuid %s already registered", lang.uuid)
        self.__langs[lang.uuid] = lang
        dispatcher.send(sender=self)
    
class HotwirePipeLanguage(PipelineLanguage):
    """The built-in Hotwire object pipeline language."""
    def __init__(self):
        super(HotwirePipeLanguage, self).__init__('62270c40-a94a-44dd-aaa0-689f882acf34',
                                                  None, "hot", "HotwirePipe", 'hotwire',
                                                  builtin_eval=True)
       
    def get_completer(self, *args, **kwargs):
        # FIXME - merge the stuff in from shell.py        
        return 'hotwire'
PipelineLanguageRegistry.getInstance().register(HotwirePipeLanguage())    
    
class PythonLanguage(PipelineLanguage):
    PYSCRIPT_CONTENT = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-

def execute(context, input):
    

if __name__ == '__main__':
  execute(None, None)
'''
    PYSCRIPT_CONTENT_LINE = 5
    def __init__(self):
        super(PythonLanguage, self).__init__('da3343a0-8bce-46ed-a463-2d17ab09d9b4',
                                             "py", "py", "Python", "python.ico", builtin_eval='py-eval',
                                             script_content=PythonLanguage.PYSCRIPT_CONTENT, 
                                             script_content_line=PythonLanguage.PYSCRIPT_CONTENT_LINE)
PipelineLanguageRegistry.getInstance().register(PythonLanguage())              
    
class RubyLanguage(PipelineLanguage):
    def __init__(self):
        super(RubyLanguage, self).__init__('e5957145-4db4-4d92-817d-379ba45adb15',
                                           "rb", "rb", "Ruby", "ruby.ico", interpreter_exec='ruby', exec_args=['-e'])
PipelineLanguageRegistry.getInstance().register(RubyLanguage())        
        
class UnixShellLanguage(PipelineLanguage):
    def __init__(self):
        super(UnixShellLanguage, self).__init__('da40fb16-4b85-4a56-a95f-022ba5281971',
                                                "sh", "sh", "Unix Shell", 'unix.ico', interpreter_exec='sh', exec_args=['-c'])
PipelineLanguageRegistry.getInstance().register(UnixShellLanguage())        
        
class PerlLanguage(PipelineLanguage):
    def __init__(self):
        super(PerlLanguage, self).__init__('467a164e-50c4-49c7-8caa-1e883f8d27da',
                                           "pl", "pl", "Perl", 'perl.ico', interpreter_exec='perl', exec_args=['-e'])
PipelineLanguageRegistry.getInstance().register(PerlLanguage())                

class PipelineFactory(object):
    def __init__(self, context, resolver=None):
        super(PipelineFactory, self).__init__()
        self.__context = context
        self.__resolver = resolver
        
    def __make_lang_pipeline(self, lang, ispiped, resolve, cmdtext):
        if ispiped:
            args = ['current', hotwire.script.PIPE]
        else:
            args = []
        if lang.builtin_eval:
            args.extend([lang.builtin_eval, cmdtext])
        else:
            args.append(lang.interpreter_exec)
            args.extend(lang.exec_args)
            args.append(cmdtext)
        pipeline = Pipeline.create(self.__context, resolve and self.__resolver or None, *args)
        return pipeline      
        
    def parse(self, text, curlang=None, resolve=True, **kwargs):
        # If input is not HotwirePipe, pass it through
        if curlang.uuid != '62270c40-a94a-44dd-aaa0-689f882acf34':
            return self.__make_lang_pipeline(curlang, False, resolve, text)
        ispiped = text.startswith('|')
        if ispiped:
            text = text[1:]        
        tokens = None
        for lang in PipelineLanguageRegistry.getInstance():
            # Skip languages which don't have a specified prefix - but we allow
            # setting them manually.
            if lang.prefix is None:
                continue
            elif not text.startswith(lang.prefix):
                continue
            _logger.debug("matched lang %r", lang)
            rest = text[len(lang.prefix):]
            if rest.strip() == '':
                scriptargs = ['hotscript', '--new', lang.uuid]
                if ispiped:
                    scriptargs.insert(0, hotwire.script.PIPE)
                    scriptargs.insert(0, 'current')
                return Pipeline.create(self.__context, resolve and self.__resolver or None, *scriptargs)
            else:
                # Require a space - should probably handle this better
                if not text.startswith(lang.prefix + " "):
                    continue
                return self.__make_lang_pipeline(lang, ispiped, resolve, rest[1:])
        # Try parsing as HotwirePipe
        if ispiped:
            text = 'current | ' + text
        return Pipeline.parse(text, context=self.__context, resolver=(resolve and self.__resolver or None), **kwargs)
