# This file is part of the Hotwire Shell user interface.
#   
# Copyright (C) 2007 Colin Walters <walters@verbum.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os,sys,platform,logging,getopt
import locale,threading,subprocess,time
import signal,tempfile,shutil

import gtk,gobject,pango
import dbus,dbus.glib,dbus.service

from hotwire.logutil import log_except
from hotvte.vteterm import VteTerminalWidget
from hotvte.vtewindow import VteWindow
from hotvte.vtewindow import VteApp

_logger = logging.getLogger("hotsudo.SudoWindow")

class AnimatedBorderBox(gtk.Bin):
    def __init__(self):
        super(AnimatedBorderBox, self).__init__()
        self.set_border_width(2)
        self.__animate_id = 0
        
    @log_except(_logger)
    def do_expose_event(self, event):
        flags = self.flags()
        if (flags & gtk.VISIBLE) and (flags & gtk.MAPPED):
            self.__paint(event.area)
        gtk.Bin.do_expose_event(self, event)
        return False
    
    def __paint(self, area):
        cr = self.window.cairo_create()
        cr.set_line_width(1)
        cr.set_source_rgb(0., 0., 0.)
        cr.rectangle(0.5, 0.5, self.allocation.width - 1, self.allocation.height - 1)
        cr.stroke()
            
    @log_except(_logger)    
    def do_size_request(self, req):
        req.width = 0
        req.height = 0
        if self.child and (self.child.flags() & gtk.VISIBLE):
            child_req = self.child.size_request()
            req.width = child_req[0]
            req.height = child_req[1]
            
        req.width += self.border_width + self.style.xthickness * 2;
        req.height += self.border_width + self.style.ythickness * 2;
        
    @log_except(_logger)
    def do_size_allocate(self, alloc):
        self.allocation = alloc
        flags = self.flags()        
        childalloc = self.__get_child_alloc()
        if flags & gtk.MAPPED and \
            (childalloc != self.child_allocation):
            self.window.invalidate_rect(self.allocation, False)
        self.child_allocation = childalloc

    def __get_child_alloc(self):
        topmargin = self.style.ythickness
        x = self.border_width + self.style.xthickness
        width = max(1, self.allocation.width - x*2)
        y = self.border_width + topmargin
        height = max(1, self.allocation.height - y - self.border_width - self.style.ythickness)
        x += self.allocation.x
        y += self.allocation.y
        return (x,y,width,height)
gobject.type_register(AnimatedBorderBox)

class SudoTerminalWidget(gtk.VBox):
    def __init__(self, args, cwd):
        super(SudoTerminalWidget, self).__init__()
        self.__cmd = ['sudo']
        self.__cmd.extend(args)
        self.__cwd = cwd
        _logger.debug("creating vte, cmd=%s cwd=%s", self.__cmd, cwd)
        self.__term = term = VteTerminalWidget(cmd=self.__cmd, cwd=cwd)
        term.connect('child-exited', self.__on_child_exited)
        term.show_all()
        self.__headerbox = gtk.HBox()
        self.pack_start(self.__headerbox, expand=False)
        #self.__borderbox = AnimatedBorderBox()
        self.pack_start(term, expand=True)# self.__borderbox, expand=True)
        #self.__borderbox.add(term)
        #self.__borderbox.show_all()        
        
    def __on_child_exited(self, term):
        _logger.debug("disconnected")
        msg = gtk.Label(_('Command exited (Enter to close)'))
        msg.set_alignment(0.0, 0.5)
        self.__headerbox.pack_start(msg)
        self.__headerbox.show_all()
        
    def get_exited(self):
        return self.__term.exited

    def get_term(self):
        return self.__term
        
    def get_vte(self):
        return self.__term.get_vte()
        
    def get_title(self):
        return ' '.join(self.__cmd)
    
    def get_cwd(self):
        return self.__cwd

class SudoWindow(VteWindow):
    def __init__(self, **kwargs):
        super(SudoWindow, self).__init__(title='HotSudo', icon_name='hotwire-sudo', **kwargs)
        
        self.__default_args = ['su', '-']
        self.__ui_string = """
<ui>
  <menubar name='Menubar'>
    <menu action='FileMenu'>
      <placeholder name='FileAdditions'>
        <menuitem action='NewTabShell'/>
      </placeholder>
    </menu>
  </menubar>
</ui>
"""
        self.__merge_sudo_ui()
        
    def new_tab(self, args, cwd):
        if not args:
            args = self.__default_args
        term = SudoTerminalWidget(args=args, cwd=cwd)
        self.append_widget(term)
        
    def __merge_sudo_ui(self):
        self.__using_accels = True
        self.__actions = actions = [
            ('NewTabShell', gtk.STOCK_NEW, 'New shell tab', '<control><shift>t',
             'Open a new tab with a shell', self.__new_tab_shell_cb),
            ]
        self._merge_ui(self.__actions, self.__ui_string)
        
    def __new_tab_shell_cb(self, action):
        notebook = self._get_notebook()
        widget = notebook.get_nth_page(notebook.get_current_page())
        cwd = widget.get_cwd()
        self.new_tab(self.__default_args, cwd=cwd)

class SudoApp(VteApp):
    def __init__(self):
        super(SudoApp, self).__init__('HotSudo', SudoWindow)
