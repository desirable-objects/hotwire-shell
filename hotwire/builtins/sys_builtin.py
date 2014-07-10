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

import os, sys, subprocess, string, threading, logging, codecs
try:
    import pty, termios, fcntl
    pty_available = True
except:
    pty_available = False

import hotwire
from hotwire.logutil import log_except
from hotwire.text import MarkupText
from hotwire.async import MiniThreadPool
from hotwire.externals.singletonmixin import Singleton
from hotwire.builtin import Builtin, BuiltinRegistry, InputStreamSchema, OutputStreamSchema, MultiArgSpec
from hotwire.sysdep import is_windows, is_unix
from hotwire.sysdep.proc import ProcessManager

if is_unix():
    import signal

_logger = logging.getLogger("hotwire.builtin.Sys")

class SystemCompleters(dict, Singleton):
    def __init__(self):
        super(SystemCompleters, self).__init__()
        
# This object is necessary because we don't want the file object
# to close the pty FD when it's unreffed.
class BareFdStreamWriter(object):
    def __init__(self, fd):
        self.fd = fd
        
    def write(self, obj):
        if isinstance(obj, unicode):
            buf = obj.encode(sys.stdout.encoding or 'UTF-8')
        else:
            buf = obj
        blen = len(buf)
        offset = 0
        count = 0
        while blen:
            count = os.write(self.fd, buf[offset:])
            offset += count
            blen -= count
            
    def close(self):
        pass

class SysBuiltin(Builtin):
    __doc__ = _("""Execute a system command, returning output as text.""")
    def __init__(self, name='sys'):
        super(SysBuiltin, self).__init__(name,
                                         input=InputStreamSchema(str, optional=True, opt_formats=['x-unix-pipe-file-object/special']),
                                         output=OutputStreamSchema(str, opt_formats=['x-unix-pipe-file-object/special',
                                                                                     'x-filedescriptor/special', 
                                                                                     'bytearray/chunked']),
                                         hasstatus=True,
                                         argspec=MultiArgSpec('args'),
                                         options_passthrough=True)

    @log_except(_logger)
    def __on_input(self, input, stream):
        try:
            for val in input.iter_avail():
                if val is None:
                    stream.close()
                    return
                stream.write(unicode(val))
        except IOError, e:
            pass
            
    @log_except(_logger)            
    def __inputwriter(self, input, stdin):
        try:
            for val in input:
                stdin.write(unicode(val))
                stdin.flush()
            stdin.close()
        except IOError, e:
            pass

    @staticmethod
    def __unbuffered_readlines(stream):
        try:
            line = stream.readline()
            while line:
                yield line
                line = stream.readline()
        except IOError, e:
            pass

    @staticmethod
    def __unbuffered_read_pipe(fd=None, stream=None):
        if fd is not None:
            fdno = fd
        else:
            fdno = stream.fileno()
        buf = os.read(fdno, 512)
        while buf:
            yield buf
            buf = os.read(fdno, 512)

    def cancel(self, context):
        if context.attribs.has_key('pid'):
            pid = context.attribs['pid']
            _logger.debug("cancelling pid %s", pid)
            ProcessManager.getInstance().terminate_pidgroup(pid)
            
    def cleanup(self, context):
        try:
            if 'input_connected' in context.attribs:
                _logger.debug("disconnecting from stdin")
                if context.input:                
                    context.input.disconnect()
                del context.attribs['input_connected']
        except:
            _logger.debug("failed to disconnect from stdin", exc_info=True)               
            pass
        try:
            if 'master_fd' in context.attribs and (not 'master_fd_passed' in context.attribs):
                os.close(context.attribs['master_fd'])
                del context.attribs['master_fd']
        except:
            _logger.debug("failed to close master fd", exc_info=True)
            pass
        
    def get_completer(self, context, args, i):
        verb = args[0].text
        _logger.debug("looking for completion for: %s", verb)
        for matcher,completer in SystemCompleters.getInstance().iteritems():
            if isinstance(matcher, basestring):
                if verb.startswith(matcher):
                    _logger.debug("matched completer %s", matcher)
                    return completer(context, args, i)

    def execute(self, context, args, in_opt_format=None, out_opt_format=None):
        # This function is complex.  There are two major variables.  First,
        # are we on Unix or Windows?  This is effectively determined by
        # pty_available, though I suppose some Unixes might not have ptys.
        # Second, out_opt_format tells us whether we want to stream the 
        # output as lines (out_opt_format is None), or as unbuffered byte chunks
        # (determined by bytearray/chunked).  There is also a special hack
        # x-filedescriptor/special where we pass along a file descriptor from
        # the subprocess; this is used in unicode.py to directly read the output.
        
        using_pty_out = pty_available and (out_opt_format not in (None, 'x-unix-pipe-file-object/special'))
        using_pty_in = pty_available and (in_opt_format is None) and \
                       context.input_is_first and hasattr(context.input, 'connect')
        _logger.debug("using pty in: %s out: %s", using_pty_in, using_pty_out)
        # TODO - we need to rework things so that we allocate only one pty per pipeline.
        # In the very common case of exactly one command, this doesn't matter, but 
        # allocating two ptys will probably bite us in odd ways if someone does create
        # a pipeline.  Maybe have a context.request_pty() function?
        if using_pty_in or using_pty_out:
            # We create a pseudo-terminal to ensure that the subprocess is line-buffered.
            # Yes, this is gross, but as far as I know there is no other way to
            # control the buffering used by subprocesses.
            (master_fd, slave_fd) = pty.openpty()
                      
            # Set the terminal to not do any processing; if you change this, you'll also
            # need to update unicode.py most likely.
            attrs = termios.tcgetattr(master_fd)
            attrs[1] = attrs[1] & (~termios.OPOST)
            termios.tcsetattr(master_fd, termios.TCSANOW, attrs)            
            
            _logger.debug("allocated pty fds %d %d", master_fd, slave_fd)
            if using_pty_out:
                stdout_target = slave_fd
            else:
                stdout_target = subprocess.PIPE
            if context.input is None:
                stdin_target = None                
            if using_pty_in:
                stdin_target = slave_fd
            elif in_opt_format == 'x-unix-pipe-file-object/special':
                stdin_target = iter(context.input).next()                
            else:
                stdin_target = subprocess.PIPE
            _logger.debug("using stdin target: %r", stdin_target)                
            context.attribs['master_fd'] = master_fd
        else:
            _logger.debug("no pty available or non-chunked output, not allocating fds")
            (master_fd, slave_fd) = (None, None)
            stdout_target = subprocess.PIPE
            if context.input is None:
                stdin_target = None
            elif in_opt_format == 'x-unix-pipe-file-object/special':
                stdin_target = iter(context.input).next()                
            else:
                stdin_target = subprocess.PIPE
            _logger.debug("using stdin target: %r", stdin_target)

        subproc_args = {'bufsize': 0,
                        'stdin': stdin_target,
                        'stdout': stdout_target,
                        'stderr': subprocess.STDOUT,
                        'cwd': context.cwd}
        
        fs_encoding = sys.getfilesystemencoding()
        stdin_encoding = sys.stdin.encoding
        _logger.debug("recoding path to %r, args to %r", fs_encoding, stdin_encoding)
        # We need to encode arguments to the system encoding because subprocess.py won't do it for us.
        if fs_encoding is not None:
            args[0] = args[0].encode(fs_encoding)
        if stdin_encoding is not None:
            args[1:] = map(lambda x: x.encode(stdin_encoding), args[1:])
        
        if is_windows():
            subproc_args['universal_newlines'] = True
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            import win32con
            startupinfo.wShowWindow = win32con.SW_HIDE            
        elif is_unix():
            subproc_args['close_fds'] = True
            # Support freedesktop.org startup notification
            # http://standards.freedesktop.org/startup-notification-spec/startup-notification-latest.txt
            if context.gtk_event_time:
                env = dict(os.environ)
                env['DESKTOP_STARTUP_ID'] = 'hotwire%d_TIME%d' % (os.getpid(), context.gtk_event_time,)
                subproc_args['env'] = env
            
            def preexec():
                os.setsid()                        
                if using_pty_out and hasattr(termios, 'TIOCSCTTY'):
                    # Set our controlling TTY
                    fcntl.ioctl(1, termios.TIOCSCTTY, '')
                # We ignore SIGHUP by default, because some broken programs expect that the lifetime
                # of subcommands is tied to an open window, instead of until when the toplevel
                # process exits.
                signal.signal(signal.SIGHUP, signal.SIG_IGN)
            subproc_args['preexec_fn'] = preexec
        else:
            assert(False)    
        subproc = subprocess.Popen(args, **subproc_args)
        if not subproc.pid:
            if master_fd is not None:
                os.close(master_fd)
            if slave_fd is not None:
                os.close(slave_fd)
            raise ValueError('Failed to execute %s' % (args[0],))
        context.attribs['pid'] = subproc.pid
        if using_pty_in or using_pty_out:
            os.close(slave_fd)            
        context.status_notify('pid %d' % (context.attribs['pid'],))
        if in_opt_format == 'x-unix-pipe-file-object/special':
            stdin_target.close()
            # If we were passed a file descriptor from another SysBuiltin, close it here;
            # it's now owned by the child.            
        elif context.input:
            if using_pty_in:
                stdin_stream = BareFdStreamWriter(master_fd)
            else:
                stdin_stream = subproc.stdin
            # FIXME hack - need to rework input streaming                
            if context.input_is_first and hasattr(context.input, 'connect'):
                context.attribs['input_connected'] = True
                context.input.connect(self.__on_input, stdin_stream)
            else:
                MiniThreadPool.getInstance().run(self.__inputwriter, args=(context.input, stdin_stream))
        if using_pty_out:
            stdout_read = None
            stdout_fd = master_fd
        else:
            stdout_read = subproc.stdout
            stdout_fd = subproc.stdout.fileno()
        if out_opt_format is None:
            for line in SysBuiltin.__unbuffered_readlines(stdout_read):
                yield line
        elif out_opt_format == 'bytearray/chunked':     
            try:
                for buf in SysBuiltin.__unbuffered_read_pipe(stream=stdout_read, fd=stdout_fd):
                    yield buf
            except OSError, e:
                pass
        elif out_opt_format == 'x-unix-pipe-file-object/special':
            yield subproc.stdout
        elif out_opt_format == 'x-filedescriptor/special':
            context.attribs['master_fd_passed'] = True            
            yield stdout_fd
        else:
            assert(False)
        retcode = subproc.wait()
        if retcode >= 0:
            retcode_str = '%d' % (retcode,)
        else:
            retcode_str = _('signal %d') % (abs(retcode),)
        context.status_notify(_('Exit %s') % (retcode_str,))
        
BuiltinRegistry.getInstance().register_hotwire(SysBuiltin())
