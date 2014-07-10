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

import os,sys,threading,pty,logging

import gtk, gobject, pango
import vte

try:
    import gconf
    gconf_available = True
except:
    gconf_available = False

_logger = logging.getLogger("hotssh.VteTerminal")

class VteTerminalScreen(gtk.Bin):
    def __init__(self):
        super(VteTerminalScreen, self).__init__()
        self.term = vte.Terminal()
        self.__termbox = gtk.HBox()
        self.__scroll = gtk.VScrollbar(self.term.get_adjustment())
        border = gtk.Frame()
        border.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        border.add(self.term)
        self.__termbox.pack_start(border)
        self.__termbox.pack_start(self.__scroll, False)
        self.add(self.__termbox)

    def do_size_request(self, req):
        (w,h) = self.__termbox.size_request()
        req.width = w
        req.height = h

    def do_size_allocate(self, alloc):
        self.allocation = alloc
        wid_req = self.__termbox.size_allocate(alloc)

gobject.type_register(VteTerminalScreen)

# From gnome-terminal src/terminal-screen.c
_USERCHARS = "-A-Za-z0-9"
_PASSCHARS = "-A-Za-z0-9,?;.:/!%$^*&~\"#'"
_HOSTCHARS = "-A-Za-z0-9"
_PATHCHARS = "-A-Za-z0-9_$.+!*(),;:@&=?/~#%"
_SCHEME = "(news:|telnet:|nntp:|file:/|https?:|ftps?:|webcal:)"
_USER = "[" + _USERCHARS + "]+(:[" + _PASSCHARS + "]+)?"
_URLPATH = "/[" + _PATHCHARS + "]*[^]'.}>) \t\r\n,\\\"]"

class VteTerminalWidget(gtk.VBox):
    __gsignals__ = {
        "child-exited" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        "fork-child" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),        
    }    
    def __init__(self, cwd=None, cmd=None, ptyfd=None, initbuf=None, **kwargs):
        super(VteTerminalWidget, self).__init__()
        
        self.__screen = screen = VteTerminalScreen()
        self.__term = screen.term
        self.pack_start(screen, expand=True)
        
        self.pid = None
        self.exited = False
        
        self.__actions = [
            ('Copy', 'gtk-copy', _('_Copy'), '<control><shift>C', _('Copy selected text'), self.__copy_cb),
            ('Paste', 'gtk-paste', _('_Paste'), '<control><shift>V', _('Paste text'), self.__paste_cb),
        ]
        self.__action_group = gtk.ActionGroup('TerminalActions')
        self.__action_group.add_actions(self.__actions)
        self.__copyaction = self.__action_group.get_action('Copy')
        self.__pasteaction = self.__action_group.get_action('Paste')         

        # Various defaults
        self.__term.set_emulation('xterm')
        self.__term.set_allow_bold(True)
        self.__term.set_size(80, 24)
        self.__term.set_scrollback_lines(1500)
        self.__term.set_mouse_autohide(True)
        
        self.__colors_default = True
        self.__term.set_default_colors()
        self.__sync_colors()

        # Use Gnome font 
        if gconf_available:
            gconf_client = gconf.client_get_default()
            def on_font_change(*args):
                mono_font = gconf_client.get_string('/desktop/gnome/interface/monospace_font_name')
                _logger.debug("Using font '%s'", mono_font)
                font_desc = pango.FontDescription(mono_font)
                self.__term.set_font(font_desc)                
            gconf_client.notify_add('/desktop/gnome/interface/monospace_font_name', on_font_change)
            on_font_change()
            
        self.__match_asis = self.__term.match_add("\\<" + _SCHEME + "//(" + _USER + "@)?[" + _HOSTCHARS + ".]+" + \
                                                  "(:[0-9]+)?(" + _URLPATH + ")?\\>/?")

        self.__match_http = self.__term.match_add("\\<(www|ftp)[" + _HOSTCHARS + "]*\\.["  + _HOSTCHARS + ".]+" + \
                                                  "(:[0-9]+)?(" + _URLPATH + ")?\\>/?")
        
        self.__term.connect('button-press-event', self.__on_button_press)
        self.__term.connect('selection-changed', self.__on_selection_changed)
        self.__on_selection_changed()

            # disable all this for now; the g-t default has an ugly foreground, let's just use
            # the theme.
#            term_profile = '/apps/gnome-terminal/profiles/Default'
#            fg_key = term_profile + '/foreground_color'
#            bg_key = term_profile + '/background_color'
#            def on_color_change():
#                if not self.__colors_default:
#                    return
#                fg = gtk.gdk.color_parse(gconf_client.get_string(fg_key))
#                self.set_color(True, fg)
#                bg = gtk.gdk.color_parse(gconf_client.get_string(bg_key))
#                self.set_color(False, bg)
#            gconf_client.notify_add(fg_key, on_color_change)
#            gconf_client.notify_add(bg_key, on_color_change)
#            on_color_change()            

        if ptyfd is not None:
            # If we have a PTY, set it up immediately
            self.__idle_do_cmd_fork(None, cwd, ptyfd, initbuf)
        else:
            # http://code.google.com/p/hotwire-shell/issues/detail?id=35
            # We do the command in an idle to hopefully have more state set up by then;
            # For example, "top" seems to be sized correctly on the first display
            # this way            
            gobject.timeout_add(250, self.__idle_do_cmd_fork, cmd, cwd, ptyfd, initbuf)
            
    def __idle_do_cmd_fork(self, cmd, cwd, ptyfd, initbuf):
        _logger.debug("Forking cmd: %s", cmd)
        self.__term.connect("child-exited", self._on_child_exited)
        if cwd:
            kwargs = {'directory': cwd}
        else:
            kwargs = {}
        if ptyfd:
            self.__term.set_pty(ptyfd)
            pid = None
        elif cmd:
            pid = self.__term.fork_command(cmd[0], cmd, **kwargs)
        else:
            pid = self.__term.fork_command(**kwargs)
        if initbuf is not None:
            self.__term.feed(initbuf)            
        self.pid = pid
        self.emit('fork-child')
        
    def __on_button_press(self, term, event):
        match = self.__term.match_check(int(event.x/term.get_char_width()), int(event.y/term.get_char_height()))
        if event.button == 1 and event.state & gtk.gdk.CONTROL_MASK:
            if not match:
                return
            (matchstr, mdata) = match            
            if mdata == self.__match_http:
                url = 'http://' + matchstr
            else:
                url = matchstr
            self.__open_url(url)
            return True
        elif event.button == 3:
            menu = gtk.Menu()
            menuitem = self.__copyaction.create_menu_item()
            menu.append(menuitem)
            menuitem = self.__pasteaction.create_menu_item()
            menu.append(menuitem)
            if match:
                (matchstr, mdata) = match
                menuitem = gtk.ImageMenuItem(_('Open Link'))
                menuitem.set_property('image', gtk.image_new_from_stock('gtk-go-to', gtk.ICON_SIZE_MENU))
                menuitem.connect('activate', lambda menu: self.__open_url(url))
                menu.append(gtk.SeparatorMenuItem())
                menu.append(menuitem)
            menu.popup(None, None, None, event.button, event.time)            
            return True
        return False             

    def __open_url(self, url):
        # Older webbrowser.py didn't check gconf
        from hotwire.sysdep import is_windows
        if sys.version_info[0] == 2 and sys.version_info[1] < 6 and (not is_windows()):
            try:
                import hotwire.externals.webbrowser as webbrowser
            except ImportError, e:
                _logger.warn("Couldn't import hotwire.externals.webbrowser", exc_info=True)
                import webbrowser
        else:
            import webbrowser            
        webbrowser.open(url)        
            
    def __on_selection_changed(self, *args):
        have_selection = self.__term.get_has_selection()
        self.__copyaction.set_sensitive(have_selection)

    def __copy_cb(self, a):
        _logger.debug("doing copy")
        self.__term.copy_clipboard()

    def __paste_cb(self, a):
        _logger.debug("doing paste")        
        self.__term.paste_clipboard()            
            
    def _on_child_exited(self, term):
        _logger.debug("Caught child exited")
        self.exited = True
        self.emit('child-exited')        
   
    def get_vte(self):
        return self.__term
    
    def get_action_group(self):
        return self.__action_group
    
    def set_copy_paste_actions(self, copyaction, pasteaction):
        """Useful in an environment where there is a global UI
        rather than a merged approach.""" 
        self.__copyaction = copyaction
        self.__pasteaction = pasteaction
    
    def __sync_colors(self):
        if self.__colors_default:
            fg = self.style.text[gtk.STATE_NORMAL]
            bg = self.style.base[gtk.STATE_NORMAL]
            self.set_color(True, fg)
            self.set_color(False, bg)
        else:
            pass # not implemented yet
        
    def set_color(self, is_foreground, color):
        if is_foreground:
            self.__term.set_color_foreground(color)
            self.__term.set_color_bold(color)
            self.__term.set_color_dim(color)            
        else:
            self.__term.set_color_background(color)

