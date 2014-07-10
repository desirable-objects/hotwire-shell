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

import os,sys,platform,logging

import gtk,gobject,pango

from hotwire.logutil import log_except
import hotwire_ui.widgets as hotwidgets
from hotwire.state import Preferences
from hotvte.vteterm import VteTerminalWidget 

_logger = logging.getLogger("hotwire.sysdep.VteTerminal")

class VteTerminalFactory(object):
    def get_terminal_widget_cmd(self, cwd, cmd, title, autoclose=False):
        return VteTerminal(cwd=cwd, cmd=cmd, title=title, autoclose=autoclose)
    
    def get_terminal_widget_ptyfd(self, cwd, ptyfd, title, initbuf=None):
        return VteTerminal(cwd=cwd, ptyfd=ptyfd, title=title, initbuf=initbuf)       

class VteTerminal(gtk.VBox):
    __gsignals__ = {
        "closed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }
    def __init__(self, cwd=None, cmd=None, title='', ptyfd=None, initbuf=None, autoclose=False):
        super(VteTerminal, self).__init__()
        self.__ui_string = """
<ui>
  <menubar name='Menubar'>
    <menu action='EditMenu'>
      <placeholder name='EditMenuAdditions'>
        <menuitem action='Copy'/>
        <menuitem action='Paste'/>
      </placeholder>
    </menu>
    <!-- <menu action='ControlMenu'>
      <menuitem action='SplitWindow'/>
    </menu> -->
  </menubar>
</ui>"""         

        self.__title = title
        self.__header = gtk.HBox()
        self.__msg = gtk.Label('')
        self.__pid = None
        self.__exited = False
        self.__autoclose = autoclose
        self.__header.pack_start(hotwidgets.Align(self.__msg, xalign=1.0), expand=False)
        self.__msg.set_property('xalign', 1.0)

        self.pack_start(self.__header, expand=False)

        prefs = Preferences.getInstance()
        prefs.monitor_prefs('term.', self.__on_pref_changed)

        termargs = {}
        if isinstance(cmd, basestring):
            termargs['cmd'] = ['/bin/sh', '-c', cmd]
        else:
            termargs['cmd'] = cmd
        if ptyfd is not None:
            termargs['ptyfd'] = ptyfd
        if initbuf is not None:
            termargs['initbuf'] = initbuf
        _logger.debug("creating term, cmd=%r", termargs['cmd'])
        self.__term = term = VteTerminalWidget(cwd=cwd, **termargs)
        self.__action_group = term.get_action_group()        
        self.pack_start(self.__term, expand=True)
        self.__term.connect('child-exited', self.__on_child_exited)
        self.__term.connect('fork-child', self.__on_fork_child)
        self.__term.get_vte().connect('key-press-event', self.__on_keypress)
         
        self.__sync_prefs()
        
    @log_except(_logger)
    def __on_keypress(self, t, e):
        if e.keyval == gtk.gdk.keyval_from_name('Return'):    
            if self.__exited:
                _logger.debug("got Return when exited")
                self.emit('closed')
                return True        
        return False
    
    def get_ui_pairs(self):
        return [(self.__ui_string, self.__action_group, None)]
        
    def __on_pref_changed(self, prefs, key, value):
        self.__sync_prefs()    
    
    def __sync_prefs(self, *args):
        prefs = Preferences.getInstance()
        fg = prefs.get_pref('term.foreground', default='#000')
        bg = prefs.get_pref('term.background', default='#FFF')
        _logger.debug("got fg=%s, bg=%s", fg, bg)
        self.set_color(True, gtk.gdk.color_parse(fg))
        self.set_color(False, gtk.gdk.color_parse(bg))
        
    def set_color(self, is_foreground, color):
        vteterm = self.__term.get_vte()
        if is_foreground:
            vteterm.set_color_foreground(color)
            vteterm.set_color_bold(color)
            vteterm.set_color_dim(color)            
        else:
            vteterm.set_color_background(color)          
        
    def __on_fork_child(self, term):
        self._set_pid(self.__term.pid)
        
    def _set_pid(self, pid):
        self.__pid = pid
        if pid is not None:
            self.__msg.set_text('Running (pid %s)' % (pid,))

    def __on_child_exited(self, term):
        _logger.debug("Caught child exited")
        self.__exited = True
        self.__msg.set_markup(_('Command exited (Enter to close)'))
        if self.__autoclose:
            self.emit('closed')
        
    def handle_detach(self):
        self.emit('closed')        

    # Used as a hack to avoid sizing issues in tabs
    def hide_internals(self):
        self.__term.hide()
        
    def show_internals(self):
        self.__term.show()

    def get_term_geometry(self):
        vteterm = self.__term.get_vte()
        cw = vteterm.get_char_width()
        ch = vteterm.get_char_height()
        return (cw, ch, vteterm.get_padding())

    def close(self):
        pass

def getInstance():
    return VteTerminalFactory()
