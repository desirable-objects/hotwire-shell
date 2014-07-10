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

import os, sys, re, logging, string

import gtk, gobject, pango

from hotwire.logutil import log_except
import hotwire_ui.widgets as hotwidgets

_logger = logging.getLogger("hotwire.ui.InlineSearch")

class InlineSearchArea(gtk.HBox):
    __gsignals__ = {
        "close" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, [])
    }

    def __init__(self, textview, **kwargs):
        super(InlineSearchArea, self).__init__(**kwargs)

        self.__textview = textview
        self.__idle_search_id = 0

        close = gtk.Button()
        close.set_focus_on_click(False)
        close.set_relief(gtk.RELIEF_NONE)
        img = gtk.Image()
        img.set_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_SMALL_TOOLBAR)
        close.add(img)
        close.connect('clicked', lambda b: self.__do_close())        
        self.pack_start(close, expand=False)
        self.__input = gtk.Entry()
        self.__input.connect("notify::text", lambda *args: self.__on_input_changed())
        self.__input.connect("key-press-event", lambda i, e: self.__on_input_keypress(e))
        self.pack_start(self.__input, expand=False)
        self.__prev = gtk.Button(_('_Back'), gtk.STOCK_GO_BACK)
        self.__prev.set_focus_on_click(False)
        self.__prev.set_relief(gtk.RELIEF_NONE)
        self.__prev.connect("clicked", lambda b: self.__do_prev())
        self.pack_start(self.__prev, expand=False)        
        self.__next = gtk.Button(_('_Forward'), gtk.STOCK_GO_FORWARD)
        self.__next.set_focus_on_click(False)
        self.__next.set_relief(gtk.RELIEF_NONE)        
        self.__next.connect("clicked", lambda b: self.__do_next())
        self.pack_start(self.__next, expand=False)

        self.__find_all = gtk.CheckButton(_('_Highlight all'))
        self.__find_all.unset_flags(gtk.CAN_FOCUS) # bigger hammer to avoid keyboard accel focus
        self.__find_all.set_focus_on_click(False)
        self.__find_all.connect('notify::active', lambda *args: self.__sync_find_all())
        self.pack_start(self.__find_all, expand=False)

        self.__msgbox = gtk.HBox()
        self.__msg_icon = gtk.Image()
        self.__msgbox.pack_start(self.__msg_icon, False)
        self.__msg = gtk.Label()
        self.__msgbox.pack_start(self.__msg, True)
        self.pack_start(self.__msgbox, expand=False)

        self.__search_tag = textview.get_buffer().create_tag("search")
        self.__sync_search_tag()
        self.connect('style-set', lambda *args: self.__sync_search_tag())

    def __on_input_keypress(self, e):
        if e.keyval == gtk.gdk.keyval_from_name('Escape'):
            self.__do_close()
            return True
        elif e.keyval in (gtk.gdk.keyval_from_name('Down'), gtk.gdk.keyval_from_name('Return')):
            self.__do_next()
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Up'):
            self.__do_prev()
            return True
        return False

    def __on_input_changed(self):
        curtext = self.__input.get_property('text')
        if not curtext:
            return
        if self.__idle_search_id == 0:
            self.__idle_search_id = gobject.timeout_add(250, self.__idle_do_search)
        self.__clear_search_selection()

    def __idle_do_search(self):
        self.__idle_search_id = 0
        self.__search(highlight_all=True)
        return False

    def __do_close(self):
        self.reset()
        self.__clear_search_selection()
        self.hide()
        self.emit("close")

    def focus(self):
        self.__input.grab_focus()
        
    def __get_search_match_colors(self):
        # TODO - use GtkSourceBuffer always and translate 
        # gedit/gedit/gedit-document.c:get_search_match_colors here
        return (None, gtk.gdk.color_parse("#FFFF78"))
        
    def __sync_search_tag(self):
        (fg, bg) = self.__get_search_match_colors()
        if fg is not None:
            self.__search_tag.set_property('foreground-gdk', fg)
        if bg is not None:
            self.__search_tag.set_property('background-gdk', bg)

    def __clear_search_selection(self):
        self.__remove_highlight()
        buf = self.__textview.get_buffer()
        buf.select_range(buf.get_start_iter(), buf.get_start_iter())
        mark = buf.get_mark("search_start")
        if mark:
            buf.delete_mark(mark)
        mark = buf.get_mark("search_end")
        if mark:
            buf.delete_mark(mark)

    def __remove_highlight(self):
        buf = self.__textview.get_buffer()
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        buf.remove_tag(self.__search_tag, start, end)

    def __sync_find_all(self):
        if not self.__find_all.get_active():        
            self.__remove_highlight()
            return

        buf = self.__textview.get_buffer()
        iter = self.__textview.get_buffer().get_start_iter()
        text = self.__input.get_text()
        
        while True:
            searchres = iter.forward_search(text, 0)
            if not searchres:
                break
            buf.apply_tag(self.__search_tag, searchres[0], searchres[1])
            iter = searchres[1]

    def reset(self):
        self.__input.set_property('text', '')
        self.__find_all.set_active(False)
        self.__msg_icon.clear()        
        self.__msg.set_text('')

    def __search(self, start_iter=None, loop=False, forward=True, highlight_all=False):
        if start_iter:
            iter = start_iter
        elif forward:
            iter = self.__textview.get_buffer().get_start_iter()
        else:
            iter = self.__textview.get_buffer().get_end_iter()
        buf = self.__textview.get_buffer()
        text = self.__input.get_text()
        if not loop:
            self.__msg_icon.clear()
            self.__msg.set_text('')
        else:
            self.__msg_icon.set_from_stock(gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.__msg.set_text('Search wrapped from top')
        if not text:
            return
        if forward:
            searchres = iter.forward_search(text, 0)
        else:
            searchres = iter.backward_search(text, 0)
        if searchres:
            if highlight_all:
                self.__sync_find_all()
            (start, end) = searchres
            buf.select_range(start, end)
            start_mark = buf.create_mark("search_start", start, False)
            end_mark = buf.create_mark("search_end", end, False)
            self.__textview.scroll_mark_onscreen(start_mark)
        elif (start_iter is not None) and (not loop):
            self.__search(loop=True, forward=forward)
        else:
            self.__msg_icon.set_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.__msg.set_text('No matches found')

    def __search_interactive(self, forward):
        if self.__idle_search_id > 0:
            gobject.source_remove(self.__idle_search_id)
            self.__idle_search_id = 0
        buf = self.__textview.get_buffer()
        if forward:
            mark = buf.get_mark("search_end")
        else:
            mark = buf.get_mark("search_start")
        if mark:
            self.__search(start_iter=buf.get_iter_at_mark(mark), forward=forward)
        else:
            self.__search(forward=forward)

    def __do_next(self):
        self.__search_interactive(True)

    def __do_prev(self):
        self.__search_interactive(False)
