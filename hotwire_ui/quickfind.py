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

from hotwire.state import Preferences
from hotwire.logutil import log_except
import hotwire_ui.widgets as hotwidgets
from hotwire_ui.pixbufcache import PixbufCache
from hotwire.state import History
from hotwire.util import markup_for_match

_logger = logging.getLogger("hotwire.ui.QuickFind")

class QuickFindWindow(gtk.Dialog):
    def __init__(self, title, parent=None):
        super(QuickFindWindow, self).__init__(title=title,
                                              parent=parent,
                                              flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                              buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_ACCEPT))
        
        self.connect('response', lambda *args: self.hide())
        self.connect('delete-event', self.hide_on_delete)
                
        self.set_has_separator(False)
        self.set_border_width(5)
        
        self.__vbox = gtk.VBox()
        self.vbox.add(self.__vbox)   
        self.vbox.set_spacing(6)
        
        self.set_size_request(640, 480)
   
        self.__response_value = None
   
        self.__idle_search_id = 0
   
        self.__entry = gtk.Entry()
        self.__entry.connect('notify::text', self.__on_text_changed)
        self.__entry.connect('key-press-event', self.__on_keypress)
        self.__vbox.pack_start(self.__entry, expand=False)
        self.__scroll = gtk.ScrolledWindow()
        self.__scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.__results = gtk.TreeView()
        self.__results.connect('row-activated', self.__on_row_activated)
        self.__scroll.add(self.__results)
        colidx = self.__results.insert_column_with_data_func(-1, '',
                                                             gtk.CellRendererPixbuf(),
                                                             self.__render_icon)
        colidx = self.__results.insert_column_with_data_func(-1, '',
                                                             hotwidgets.CellRendererText(ellipsize=True),
                                                             self.__render_match)        
        self.__vbox.pack_start(hotwidgets.Border(self.__scroll), expand=True)
        self.__selection = self.__results.get_selection()
        self.__selection.set_mode(gtk.SELECTION_SINGLE)
        self.__selection.connect('changed', self.__on_selection_changed)
        self.__results.set_headers_visible(False)
        
        self.__do_search()
        
    def __on_keypress(self, entry, event):
        if event.keyval == gtk.gdk.keyval_from_name('Return'):
            self.__idle_do_search()
            return self.__activate_selection()
        elif event.keyval == gtk.gdk.keyval_from_name('Up'):
            self.__idle_do_search()
            self.__select_next()
            return True
        elif event.keyval == gtk.gdk.keyval_from_name('Down'):
            self.__idle_do_search()
            self.__select_prev()
            return True
        return False        
        
    def __on_text_changed(self, *args):
        if self.__idle_search_id > 0:
            return
        self.__idle_search_id = gobject.timeout_add(300, self.__idle_do_search)
        
    def __idle_do_search(self):
        if self.__idle_search_id == 0:
            return False
        self.__idle_search_id = 0
        self.__do_search()
        return False
        
    def _markup_search(self, text, searchq, text_lower=None, searchq_lower=None):
        if text_lower is not None:
            idx = text_lower.find(searchq_lower)
        else:
            idx = text.find(searchq)
        if idx >= 0:
            return markup_for_match(text, idx, idx+len(searchq))
        else:
            return None          
        
    def _get_string_data(self):
        """Generate a list of strings for search data."""
        raise NotImplementedError()
    
    def _do_search(self, text):
        """Override this to implement a custom search with icons, etc."""
        strings = self._get_string_data()
        text = text.lower()
        for s in strings:
            if s.lower().find(text) >= 0:
                yield (s, s, None)
        
    def __do_search(self):
        text = self.__entry.get_property('text')
        results = self._do_search(text)
        model = gtk.ListStore(gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT)
        have_results = False
        for result in results:
            have_results = True
            _logger.debug("appending result: %s", result)
            model.append(result)
        self.__results.set_model(model)
        if have_results:
            self.__selection.select_iter(model.get_iter_first())            
        
    def __on_selection_changed(self, sel):
        (model, iter) = sel.get_selected()
        if iter:
            self.__results.scroll_to_cell(model.get_path(iter))
            
    def __get_selected_path(self):
        (model, iter) = self.__selection.get_selected()
        return iter and model.get_path(iter)
        
    def __select_next(self):
        path = self.__get_selected_path()
        if not path:
            return
        previdx = path[-1]-1
        if previdx < 0:
            return
        model = self.__results.get_model()        
        previter = model.iter_nth_child(None, previdx)
        if not previter:
            return
        self.__selection.select_iter(previter)
        
    def __select_prev(self):
        path = self.__get_selected_path()
        if not path:
            return
        model = self.__results.get_model()        
        seliter = model.get_iter(path)
        iternext = model.iter_next(seliter)
        if not iternext:
            return
        self.__selection.select_iter(iternext)
        
    def __activate_selection(self):
        (model, iter) = self.__selection.get_selected()
        if not iter:
            return False
        self._handle_activation(model.get_value(iter, 0))
        return True        
        
    @log_except(_logger)
    def __on_row_activated(self, tv, path, vc):
        _logger.debug("row activated: %s", path)
        model = self.__results.get_model()
        iter = model.get_iter(path)
        self._handle_activation(model.get_value(iter, 0))
    
    def __render_match(self, col, cell, model, iter):
        markup = model.get_value(iter, 1)
        if markup:
            cell.set_property('markup', markup)
        else:
            cell.set_property('text', model.get_value(iter, 0))    
    
    def __render_icon(self, col, cell, model, iter):
        icon_name = model.get_value(iter, 2)
        if icon_name:
            pbcache = PixbufCache.getInstance()
            pixbuf = pbcache.get(icon_name, size=16, trystock=True, stocksize=gtk.ICON_SIZE_MENU)
            cell.set_property('pixbuf', pixbuf)
        else:
            cell.set_property('icon-name', None)    
    
    def get_response_value(self):
        return self.__response_value
        
    def _handle_activation(self, val):
        self.__response_value = val
        self.response(gtk.RESPONSE_ACCEPT)
    
    def run_get_value(self):
        self.show_all()
        resp = self.run()
        if resp == gtk.RESPONSE_ACCEPT:
            return self.__response_value
        return None
