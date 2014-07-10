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

import os,sys,logging,locale,codecs,gettext

# Older webbrowser.py didn't check gconf
from hotwire.sysdep import is_windows
if sys.version_info[0] == 2 and sys.version_info[1] < 6 and (not is_windows()):
    import hotwire.externals.webbrowser as webbrowser
else:
    import webbrowser

import gtk, gobject, pango

import hotwire
from hotwire.sysdep import is_unix, is_windows
from hotwire.text import MarkupText
from hotwire.logutil import log_except
import hotwire_ui.widgets as hotwidgets
from hotwire_ui.inlinesearch import InlineSearchArea
from hotwire_ui.render import ObjectsRenderer, ClassRendererMapping

_logger = logging.getLogger("hotwire.ui.render.Unicode")

class InputArea(gtk.HBox):
    __gsignals__ = {
        "close" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, []),
        "object-input" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,gobject.TYPE_BOOLEAN)),  
    }

    def __init__(self, renderer, textview, **kwargs):
        super(InputArea, self).__init__(**kwargs)

        self.__renderer = renderer
        self.__textview = textview
        
        # Whether the user manually changed the password mode - if so, take it off auto
        self.__override_password_mode = False
        # Whether we're modifying password mode programatically
        self.__doing_auto_password_mode = False

        close = gtk.Button()
        close.set_focus_on_click(False)
        close.set_relief(gtk.RELIEF_NONE)
        img = gtk.Image()
        img.set_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_SMALL_TOOLBAR)
        close.add(img)
        close.connect('clicked', lambda b: self.__do_close())        
        self.pack_start(close, expand=False)
        self.__input = gtk.Entry()
        self.__input.connect("key-press-event", lambda i, e: self.__on_input_keypress(e))
        hbox = gtk.HBox()
        hbox.pack_start(self.__input, expand=True)
        self.__send= gtk.Button('_Send', gtk.STOCK_OK)
        self.__send.set_focus_on_click(False)
        self.__send.connect("clicked", lambda b: self.__do_send())
        hbox.pack_start(self.__send, expand=False)
        self.__password_button = gtk.CheckButton(label=_('_Password mode'))
        self.__password_button.connect('toggled', self.__on_password_toggled)
        self.__password_button.set_focus_on_click(False)
        hbox.pack_start(hotwidgets.Align(self.__password_button, padding_left=8), expand=False)
        self.pack_start(hotwidgets.Align(hbox, xscale=0.75), expand=True)        

    def __on_input_keypress(self, e):
        self.__recheck_password_mode()
        if e.keyval == gtk.gdk.keyval_from_name('Escape'):
            self.__do_close()
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Return'):
            self.__do_send()
            return True      
        return False
    
    def __on_password_toggled(self, tb):
        if not self.__doing_auto_password_mode:
            self.__override_password_mode = True
        self.__input.set_visibility(not tb.get_active())

    def __do_close(self):
        self.reset()
        self.hide()
        self.__override_password_mode = False
        self.emit("close")
        
    def __do_send(self):
        obj = unicode(self.__input.get_property('text') + '\n')
        self.emit('object-input', obj, self.__password_button.get_active())
        self.reset()
        
    def __recheck_password_mode(self):
        if self.__override_password_mode:
            return
        self.__doing_auto_password_mode = True
        self.__password_button.set_active(self.__renderer.get_default_password_mode())
        self.__doing_auto_password_mode = False

    def focus(self):
        self.__recheck_password_mode()
        self.__input.grab_focus()

    def reset(self):
        self.__input.set_property('text', '')

class UnicodeRenderer(ObjectsRenderer):
    def __init__(self, context, monospace=True, **kwargs):
        super(UnicodeRenderer, self).__init__(context, **kwargs)
        self._buf = hotwidgets.BasicMarkupTextBuffer()
        self.__text = gtk.TextView(self._buf)
        if monospace:
            self.__text.modify_font(pango.FontDescription("monospace"))
        self.__text.connect('event-after', self.__on_event_after)
        self._buf.connect('mark-set', self.__on_mark_set)
        self.__term = None
        self.__wrap_lines = True
        self.__have_selection = False
        self.__sync_wrap()
        self.__text.set_editable(False)
        self.__text.set_cursor_visible(False)
        self.__text.unset_flags(gtk.CAN_FOCUS)
        self.__empty = True
        if sys.version_info[0] == 2 and sys.version_info[1] < 5:
            # No incremental decoding in Python 2.4 =/
            self.__locale_decoder = None
        else:
            (lcode, locale_encoding) = locale.getdefaultlocale()
            if locale_encoding and locale_encoding.lower() == 'utf-8':
                # This is the ideal, running on a UTF-8 system.
                self.__locale_decoder = None
            else:
                if not locale_encoding:
                    _logger.debug("No locale set: using C locale")
                    locale_encoding = 'ascii'
                _logger.debug("creating decoder for locale encoding %r", locale_encoding)
                self.__locale_decoder = codecs.getincrementaldecoder(locale_encoding)()
        
        # This is an optimization; we pass in a file descriptor from sys_builtin.py,
        # and then poll it here for maximum efficiency. 
        self.__subproc_fd = None
        self.__subproc_stream = None
        
        self._buf.insert_markup("<i>(No output)</i>")
        self.__search = InlineSearchArea(self.__text)
        self.__inputarea = InputArea(self, self.__text)
        #self.__inputarea.connect('object-input', self.__on_object_input)
        self.__text.connect('populate-popup', self.__on_populate_popup)
        self.__links = {} # internal hyperlinks
        self.__support_links = False
        self.__hovering_over_link = False
        
    def __on_object_input(self, ia, o, pwmode):
        # We're relying on terminal echo now.
        return
        #if not pwmode:
        #    self.append_obj(o)

    def __on_event_after(self, textview, e):
        if e.type != gtk.gdk.BUTTON_RELEASE:
            return;
        if e.button != 1:
            return;
        (x, y) = self.__text.window_to_buffer_coords(gtk.TEXT_WINDOW_WIDGET, int(e.x), int(e.y))
        iter = self.__text.get_iter_at_location(x, y)
        for tag in iter.get_tags():
            if tag.get_property('name') == 'link':
                iterstart = iter.copy()
                iterend = iter.copy()
                iterstart.backward_to_tag_toggle(tag)
                iterend.forward_to_tag_toggle(tag)
                bufslice = self._buf.get_slice(iterstart, iterend)
                linkvalue = self.__links[bufslice]
                if isinstance(linkvalue, basestring):
                    webbrowser.open(linkvalue)
                elif hasattr(linkvalue, '__call__'):
                    linkvalue(bufslice)
                break

    def append_link(self, text, target):
        self.__links[text] = target
        if not self.__support_links:
            self.__install_link_handlers()
            self.__support_links = True
        (iterstart, iterend) = self._buf.get_bounds()
        self._buf.insert_with_tags_by_name(iterend, text, 'link')

    def __install_link_handlers(self):
        self.__text.connect('motion-notify-event', self.__on_motion_notify)
        self.__text.connect('visibility-notify-event', self.__on_visibility_notify)

    def __on_motion_notify(self, text, e):
        (x, y) = self.__text.window_to_buffer_coords(gtk.TEXT_WINDOW_WIDGET, int(e.x), int(e.y))
        self.__update_cursor_for_coords(x, y)
        (x, y, state) = self.__text.window.get_pointer()
        
    def __on_visibility_notify(self, text, vis):
        (x, y) = self.__text.get_pointer()
        self.__update_cursor_for_coords(x, y)
        
    def __on_mark_set(self, *args):
        have_sel = not not self._buf.get_selection_bounds()
        if have_sel == self.__have_selection:
            return
        self.context.get_ui().get_action('/Menubar/EditMenu/EditMenuAdditions/Copy').set_sensitive(have_sel)
        self.__have_selection = have_sel

    def __update_cursor_for_coords(self, x, y):
        iter = self.__text.get_iter_at_location(x, y)
        hovering = False
        for tag in iter.get_tags():
            if tag.get_property('name') == 'link':
                hovering = True
                break
        if hovering != self.__hovering_over_link:
            self.__hovering_over_link = hovering
            if hovering:
                cursor = gtk.gdk.Cursor(self.__text.get_display(), gtk.gdk.HAND2)
            else:
                cursor = None
            window = self.__text.get_window(gtk.TEXT_WINDOW_TEXT)
            window.set_cursor(cursor)
        
    def get_widget(self):
        return self.__text

    def get_search(self):
        return self.__search

    def get_status_str(self):
        if self.__empty:
            charcount = 0
        else:
            charcount = self._buf.get_char_count()
        return gettext.ngettext('%d character' % (charcount,), '%d characters' % (charcount,), charcount)

    def __get_objects_from_iters(self, start, end):
        if self.__empty:
            return
        if start == end:
            return
        iter = start
        realend = self._buf.get_end_iter()
        while iter.compare(end) < 0:
            startline = iter 
            iter = iter.copy()
            not_at_end = iter.forward_line()
            at_realend = iter.compare(realend) == 0            
            if iter.compare(end) > 0:
                not_at_end = False
                iter = end
            yield self._buf.get_slice(startline, iter)

    def get_objects(self):
        for o in self.__get_objects_from_iters(self._buf.get_start_iter(), self._buf.get_end_iter()):
            yield o
    
    def get_selected_objects(self):
        bounds = self._buf.get_selection_bounds()
        if not bounds:
            return
        for o in self.__get_objects_from_iters(bounds[0], bounds[1]):
            yield o

    def get_opt_formats(self):
        if is_unix():
            return ['x-filedescriptor/special', 'bytearray/chunked']
        else:
            return ['bytearray/chunked']
        
    def __append_locale_chunk(self, obj, flush=False):
        if self.__locale_decoder is None:
            self.__append_chunk(obj)
        else:
            decoded = self.__locale_decoder.decode(obj, flush)
            self.__append_chunk(decoded)

    def __append_chunk(self, obj):
        buf = self._buf
        if self.__empty:
            buf.delete(buf.get_start_iter(), buf.get_end_iter())
            self.__empty = False
        buf.insert(buf.get_end_iter(), obj)
        self.emit('status-changed')

    def append_obj(self, obj, fmt=None):
        # If you change format types, be sure to update odisp.py:append_object
        if fmt == 'bytearray/chunked':
            self.__append_locale_chunk(obj)
            return
        elif fmt == 'x-filedescriptor/special':
            self.__subproc_fd = obj
            self.__monitor_fd(obj)
            return        
        if self.__empty:
            self._buf.delete(self._buf.get_start_iter(), self._buf.get_end_iter())
            self.__empty = False
        allinsert_start = self._buf.get_start_iter().get_offset()
        if isinstance(obj, MarkupText):
            tags = []
            prev_tagend = 0
            olen = len(obj)
            for (tagname, start, end) in obj.markup:
               self._buf.insert(self._buf.get_end_iter(), obj[prev_tagend:start])
               real_end = (end == -1) and olen or end
               self._buf.insert_with_tags_by_name(self._buf.get_end_iter(), obj[start:real_end], tagname)
               prev_tagend = real_end
            self._buf.insert(self._buf.get_end_iter(), obj[prev_tagend:])
        else:
            self.__append_chunk(obj)
        
    def __spawn_terminal(self, fd, buf):
        # Undo terminal mode changes from sys_builtin.py
        import termios
        attrs = termios.tcgetattr(fd)
        # If you change this, be sure to update sys_builtin.py
        attrs[1] = attrs[1] | (termios.OPOST)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        buf = buf.replace('\n', '\r\n')        
                
        from hotwire_ui.shell import locate_current_window
        title = 'Terminal' # FIXME
        hotwin = locate_current_window(self.__text)
        from hotwire.sysdep.term import Terminal
        term = Terminal.getInstance().get_terminal_widget_ptyfd(None, fd, title, initbuf=buf)
        hotwin.new_win_widget(term, title)
        self._buf.insert_markup('\n\n<b>(%s)</b>' % (_('Entered Terminal Compatibility Mode'),))

    @log_except(_logger)
    def __on_fd(self, src, condition):
        have_eof_or_err = (condition & gobject.IO_HUP) or (condition & gobject.IO_ERR)
        if (condition & gobject.IO_IN):
            buf = os.read(src, 8192)
            try:
                self.__append_locale_chunk(buf, flush=have_eof_or_err)
            except:
                pass
        if have_eof_or_err:
            try:
                os.close(src)
                self.__subproc_fd = None
            except:
                pass
            return False
        return True        
        
    def __monitor_fd(self, fd):
        gobject.io_add_watch(fd, gobject.IO_IN | gobject.IO_ERR | gobject.IO_HUP, self.__on_fd, priority=gobject.PRIORITY_LOW)
        
    def get_default_password_mode(self):
        if self.__subproc_fd is None:
            return False
        import termios
        attrs = termios.tcgetattr(self.__subproc_fd)
        echoflag = attrs[3] & (termios.ECHO)
        _logger.debug("echo flag is %s", echoflag) 
        return echoflag == 0      

    def get_autoscroll(self):
        return True

    def can_copy(self):
        return self._buf.get_selection_bounds()

    def do_copy(self):
        bounds = self._buf.get_selection_bounds()
        if bounds:
            self._buf.copy_clipboard(gtk.Clipboard())
            return True
        return False
        
    def __sync_wrap(self):
        self.__text.set_wrap_mode(self.__wrap_lines and gtk.WRAP_CHAR or gtk.WRAP_NONE)

    def __on_toggle_wrap(self, menuitem):
        self.__wrap_lines = not self.__wrap_lines
        self.__sync_wrap()
        
    def __on_save_output(self, menuitem):
        dlg = gtk.FileChooserDialog(title=_('Save Output As...'),
                                    action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                    buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
        dlg.set_default_response(gtk.RESPONSE_ACCEPT)
        dlg.set_property('do-overwrite-confirmation', True)
        resp = dlg.run()
        try:
            if resp != gtk.RESPONSE_ACCEPT:
                return
            path = dlg.get_filename()
            f = open(path, 'w')
            try:
                if not self.__empty:             
                    f.write(self._buf.get_property('text'))
            finally:
                f.close()
        finally:
            dlg.destroy()

    def __on_populate_popup(self, textview, menu):
        menuitem = gtk.SeparatorMenuItem()
        menuitem.show_all()
        menu.prepend(menuitem)        
        menuitem = gtk.ImageMenuItem(_('Save Output As...'))  
        menu.prepend(menuitem)        
        menuitem.set_property('image', gtk.image_new_from_stock('gtk-save', gtk.ICON_SIZE_MENU))
        menuitem.connect("activate", self.__on_save_output)
        menuitem.show_all()        
        menuitem = gtk.SeparatorMenuItem()
        menuitem.show_all()
        menu.prepend(menuitem)
        menuitem = gtk.CheckMenuItem(label=_('_Wrap lines'), use_underline=True) 
        menuitem.set_active(self.__wrap_lines)
        menuitem.connect("activate", self.__on_toggle_wrap)
        menuitem.show_all()
        menu.prepend(menuitem)
        menuitem = self.context.get_ui().get_action('/Menubar/EditMenu/EditMenuAdditions/Input').create_menu_item()
        menuitem.show_all()
        menu.prepend(menuitem) 

    def supports_input(self):
        return True
    
    def get_input(self):
        return self.__inputarea

ClassRendererMapping.getInstance().register(unicode, UnicodeRenderer)
ClassRendererMapping.getInstance().register(str, UnicodeRenderer) # for now
