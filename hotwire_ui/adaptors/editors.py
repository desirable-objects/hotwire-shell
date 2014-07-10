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

import os,sys,subprocess,logging,re

import gtk

from hotwire.util import quote_arg
from hotwire.logutil import log_except
from hotwire.externals.singletonmixin import Singleton
from hotwire.state import Preferences
from hotwire.externals.dispatch import dispatcher

_logger = logging.getLogger('hotwire.ui.adaptors.Editors')

class Editor(object):
    """Abstract superclass of external editors."""
    uuid = property(lambda self: self._uuid, doc="""Unique identifer for this editor.""")
    name = property(lambda self: self._name, doc="""Human-readable name for the editor.""")
    icon = property(lambda self: self._icon, doc="""Icon name for this editor; may be absolute or stock.""")
    executable = property(lambda self: self._executable, doc="""Executable program, may be a path.""")
    args = property(lambda self: self._args, doc="""Default arguments for program.""")
    requires_terminal = property(lambda self: self._requires_terminal, doc="""Whether or not this program should be run in a terminal.""")
    goto_line_arg_prefix = property(lambda self: self._goto_line_arg, doc="""Prefix argument required to jump to a specific line number.""")
    goto_line_arg = property(lambda self: self._goto_line_arg, doc="""Full argument required to jump to a specific line number.""")
    read_only_arg = property(lambda self: self._read_only_arg, doc="""Argument for using read-only mode.""")
    
    def __init__(self, uuid, name, icon, executable, args=[]):
        super(Editor, self).__init__()
        self._uuid = uuid
        self._name = name
        self._icon = icon
        self._executable = executable
        self._args = args        
        self._requires_terminal = False
        self._goto_line_arg_prefix = '+'
        self._goto_line_arg = None
        self._read_only_arg = None
        
    def _get_startup_env(self):
        env = dict(os.environ)
        env['DESKTOP_STARTUP_ID'] = 'hotwire%d_TIME%d' % (os.getpid(), gtk.get_current_event_time(),)
        return env
    
    @log_except(_logger)
    def __idle_run_cb(self, pid, condition, cb):
        cb()
        return False
    
    def build_default_arguments(self, readonly=False):
        args = [self.executable]
        if readonly and self._read_only_arg is not None:
            args.append(self._read_only_arg)
        args.extend(self._args)
        return args
    
    def build_arguments(self, file, lineno, **kwargs):
        args = self.build_default_arguments(**kwargs)
        if lineno >= 0:
            if self.goto_line_arg_prefix:
                args.append('%s%d', self.goto_line_arg_prefix, lineno)
            elif self.goto_line_arg:
                args.extend([self.goto_line_arg, '%d' % (lineno,)])
        args.append(file)
        return args
    
    def run(self, cwd, file, **kwargs):
        self.run_with_callback(cwd, file, None, **kwargs)
        
    def run_many(self, cwd, *files):
        args = self.build_default_arguments()
        args.extend(files)
        subprocess.Popen(args, env=self._get_startup_env(), cwd=cwd)
        
    def run_many_readonly(self, cwd, *files):
        args = self.build_default_arguments(readonly=True)
        args.extend(files)
        subprocess.Popen(args, env=self._get_startup_env(), cwd=cwd)        
        
    def run_sync(self, cwd, file, **kwargs):
        args = self.build_arguments(file, lineno)
        retcode = subprocess.call(args, env=self._get_startup_env(), cwd=cwd)
        return retcode
        
    def run_with_callback(self, cwd, file, callback, lineno=-1):
        args = self.build_arguments(file, lineno)
        proc = subprocess.Popen(args, env=self._get_startup_env(), cwd=cwd)
        if callback:
            gobject.child_watch_add(proc.pid, self.__idle_run_cb, callback)

class EditorRegistry(Singleton):
    """Registry for supported external editors."""
    def __init__(self):
        self.__editors = {} # uuid->editor
        prefs = Preferences.getInstance()
        self.__default_editor_uuid = 'c5851b9c-2618-4078-8905-13bf76f0a94f'
        self.__custom_editor_uuid = '5f8d7da1-fa4f-4753-8541-be58485af722'
        self.__custom_editor_set = 'EDITOR' in os.environ        
        self.__sync_pref()
        prefs.monitor_prefs('system.editor', self.__on_editor_changed)
        
    def __sync_pref(self):
        prefs = Preferences.getInstance()
        if self.__custom_editor_set:
            self.__pref_editor_uuid = self.__custom_editor_uuid
        else:
            self.__pref_editor_uuid = prefs.get_pref('system.editor', default=self.__default_editor_uuid)        
        
    def __on_editor_changed(self, *args, **kwargs):
        self.__custom_editor_set = False             
        self.__sync_pref()
        editor = ' '.join(map(quote_arg, self[self.__pref_editor_uuid].build_default_arguments()))
        if isinstance(editor, unicode) and sys.stdin.encoding is not None:
            editor = editor.encode(sys.stdin.encoding)
        os.environ['EDITOR'] = editor
        
    def __sync_environ(self):
        'hotwire-runeditor ' + ' '.join()        
        
    def get_preferred(self):
        if self.__pref_editor_uuid:
            return self[self.__pref_editor_uuid]
        return None
    
    def set_preferred(self, editor):
        prefs = Preferences.getInstance()
        prefs.set_pref('system.editor', editor.uuid)
        
    def __getitem__(self, uuid):
        return self.__editors[uuid]
        
    def __iter__(self):
        for x in self.__editors.itervalues():
            yield x

    def register(self, editor):
        if editor.uuid in self.__editors:
            raise ValueError("Editor uuid %s already registered", editor.uuid)
        self.__editors[editor.uuid] = editor
        if editor.uuid == self.__pref_editor_uuid and not self.__custom_editor_set:
            self.__on_editor_changed()
        dispatcher.send(sender=self)

class HotwireEditor(Editor):
    def __init__(self):
        super(HotwireEditor, self).__init__('c5851b9c-2618-4078-8905-13bf76f0a94f', 'Hotwire Edit',
                                            'hotwire', 'hotwire-editor')
        self._read_only_arg = '-r'
EditorRegistry.getInstance().register(HotwireEditor())    
        
class GVimEditor(Editor):
    def __init__(self):
        super(GVimEditor, self).__init__('eb88b728-42d1-4dc0-a20b-c885497520a2', 'GVim', 'gvim.png', 'gvim',
                                         args=['--remote-wait'])
        self._read_only_arg = '-R'
EditorRegistry.getInstance().register(GVimEditor())

class EmacsClientEditor(Editor):
    def __init__(self):
        super(EmacsClientEditor, self).__init__('8acfcef3-9d05-47e8-86a1-b005fa8897ec', 'Emacs (client)', 'emacs.png', 'emacsclient')
EditorRegistry.getInstance().register(EmacsClientEditor())

class GEditEditor(Editor):
    def __init__(self):
        super(GEditEditor, self).__init__('781e8969-730e-42f7-bd1d-a50bed17e869', 'GEdit', 'accessories-text-editor', 
                                          'hotwire-gedit-blocking')
EditorRegistry.getInstance().register(GEditEditor())

class CustomEditor(Editor):
    def __init__(self):
        super(CustomEditor, self).__init__('5f8d7da1-fa4f-4753-8541-be58485af722', 'Custom Editor', None, None)
        
    def run_many(self, cwd, *files):
        # FIXME do real shell parsing
        ws_re = re.compile('\s+')
        args = ws_re.split(os.environ['EDITOR'])
        args.extend(files)
        subprocess.Popen(args, env=self._get_startup_env(), cwd=cwd)        
EditorRegistry.getInstance().register(CustomEditor())
