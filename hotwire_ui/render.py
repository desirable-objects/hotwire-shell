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

import sys, os, logging

import gtk, gobject

import hotwire
from hotwire.externals.singletonmixin import Singleton
from hotwire_ui.pixbufcache import PixbufCache
import hotwire_ui.widgets as hotwidgets

_logger = logging.getLogger("hotwire.ui.Render")

def menuitem(name=None):
    def addtypes(f):
        setattr(f, 'hotwire_menuitem', name)
        return f
    return addtypes

class ClassRendererMapping(Singleton):
    def __init__(self):
        self.__map = {}

    def lookup(self, cls, context=None):
        try:
            return self.__map[cls](context=context)
        except KeyError:
            for base in cls.__bases__:
                result = self.lookup(base, context=context)
                if result:
                    return result
        return None

    def register(self, cls, target_class):
        self.__map[cls] = target_class

class ObjectsRenderer(gobject.GObject):  
    __gsignals__ = {
        "status-changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }
    def __init__(self, context):
        super(ObjectsRenderer, self).__init__()
        self.context = context

    def get_widget(self):
        raise NotImplementedError()

    def get_opt_formats(self):
        return []

    def append_obj(self, obj, **kwargs):
        raise NotImplementedError()

    def get_autoscroll(self):
        return False

    def get_status_str(self):
        return None

    def get_objects(self):
        raise NotImplementedError()
    
    def get_selected_objects(self):
        raise NotImplementedError()    

    def start_search(self):
        raise NotImplementedError()

    def get_search(self):
        raise NotImplementedError()
    
    def do_copy(self):
        return False
    
    def supports_input(self):
        return False
    
    def get_input(self):
        raise NotImplementedError()

class TreeObjectsRenderer(ObjectsRenderer):
    def __init__(self, context, column_types=None, **kwargs): 
        super(TreeObjectsRenderer, self).__init__(context, **kwargs)
        self.__search_enabled = False
        self._linkcolumns = []
        if column_types:
            ctypes = column_types
        else:
            ctypes = [gobject.TYPE_PYOBJECT]
        self.context = context
        self._liststore = gtk.ListStore(*ctypes)
        self._model = gtk.TreeModelSort(self._liststore)
        self._table = gtk.TreeView(self._model)
        #self._table.unset_flags(gtk.CAN_FOCUS)        
        self._table.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self._table.add_events(gtk.gdk.BUTTON_PRESS_MASK)      
        self._table.connect("button-press-event", self.__on_button_press)        
        self._table.connect("row-activated", self.__on_row_activated)
        self._setup_view_columns()
        self.__selected_obj = None

    def __get_func_menuitems(self, iter):
        menuitems = []
        for item in self.__class__.__dict__:
            attrval = getattr(self, item)
            if hasattr(attrval, '__call__'):
                if hasattr(attrval, 'hotwire_menuitem'):
                    name = getattr(attrval, 'hotwire_menuitem') or (attrval.func_name[0].upper() + attrval.func_name[1:])
                    menuitems.append((attrval, name))
        func_menuitems = []
        for (item, name) in menuitems:
            menuitem = gtk.MenuItem(label=name) 
            menuitem.connect("activate", self.__do_menuitem, item, iter)
            func_menuitems.append(menuitem)
        return func_menuitems

    def __do_menuitem(self, menuitem, func, iter):
        func(iter)
        self.context.push_msg('Execution of <b>%s</b> successful' % (gobject.markup_escape_text(func.func_name),),
                              markup=True)

    def get_widget(self):
        return self._table

    def get_objects(self):
        iter = self._model.get_iter_first()
        while iter:
            val = self._model.get_value(iter, 0)
            yield val
            iter = self._model.iter_next(iter)
            
    def get_selected_objects(self):
        (model, rows) = self._table.get_selection().get_selected_rows()
        for row in rows:
            yield model[row][0]

    def _setup_view_columns(self):
        colidx = self._table.insert_column_with_data_func(-1, 'Object',
                                                       hotwidgets.CellRendererText(ellipsize=True),
                                                       self._render_objtext)
        col = self._table.get_column(colidx-1)
        col.set_resizable(True)

    def _insert_column(self, name, proptype=None,
                         title=None, renderer=None, 
                         renderfunc=None, idx=0,
                         valuefunc=None, sortfunc=None, **kwargs):
        if title is None:
            target_title = (name[0].upper() + name[1:])
        else:
            target_title = title
        colidx = self._table.insert_column_with_data_func(-1, title,
                                                          renderer or hotwidgets.CellRendererText(**kwargs),
                                                          renderfunc or self._render_propcol, (name, idx))
        col = self._table.get_column(colidx-1)
        col.set_data('hotwire-propname', name)
        col.set_data('hotwire-proptype', proptype)
        col.set_resizable(True)
        col.set_sort_column_id(colidx - 1)        
        if sortfunc:
            self._model.set_sort_func(colidx-1, sortfunc)
        else:
            self._model.set_sort_func(colidx-1, self._default_compare, (idx, valuefunc or (lambda x: getattr(x, name))))
        return col        

    def _insert_proptext(self, name, title=None, **kwargs):
        return self._insert_column(name, proptype=unicode, title=title, renderfunc=self._render_proptext, **kwargs)

    def _insert_propcol(self, name, title=None, idx=0, **kwargs):
        return self._insert_column(name, proptype='any', title=title, renderfunc=self._render_propcol, **kwargs)

    def _get_propcol_by_name(self, name):
        for column in self._table.get_columns():
            colname = column.get_data('hotwire-propname')
            if colname == name:
                return column
        raise KeyError(name)

    def _default_compare(self, model, iter1, iter2, args):
        (idx, value_func) = args        
        obj1 = model.get_value(iter1, idx)
        obj2 = model.get_value(iter2, idx)
        if obj1 is None and obj2 is not None:
            return 1
        elif obj1 is not None and obj2 is None:
            return -1
        value1 = value_func(obj1)
        value2 = value_func(obj2)
        return cmp(value1, value2)

    def _set_search_column(self, col):
        colidx = -1
        for i,c in enumerate(self._table.get_columns()):
            if c == col:
                colidx = i
                break
        assert colidx != -1
        self.__search_enabled = True
        self._table.set_search_column(colidx)
        self._table.set_search_equal_func(col.get_data('hotwire-proptype') is unicode and self._search_proptext or self._search_propcol,
                                          col.get_data('hotwire-propname'))

    def _render_propcol(self, col, cell, model, iter, data):
        (prop, idx) = data        
        obj = model.get_value(iter, idx)
        propval = getattr(obj, prop)
        cell.set_property('text', unicode(propval))

    def _render_proptext(self, col, cell, model, iter, data):
        (prop, idx) = data
        obj = model.get_value(iter, 0)
        propval = getattr(obj, prop)
        cell.set_property('text', propval)

    def _render_icon(self, col, cell, model, iter, data):
        (prop, idx) = data
        obj = model.get_value(iter, idx)
        icon_name = getattr(obj, prop)
        if icon_name:
            if icon_name.startswith(os.sep):
                pixbuf = PixbufCache.getInstance().get(icon_name)
                cell.set_property('pixbuf', pixbuf)
            else:
                cell.set_property('icon-name', icon_name)
        else:
            cell.set_property('icon-name', None)

    def _search_propcol(self, model, col, key, iter, prop):
        obj = model.get_value(iter, 0)
        propval = getattr(obj, prop)
        text = unicode(propval) 
        if text.find(key) >= 0:
            return False
        return True

    def _search_proptext(self, model, col, key, iter, prop):
        obj = model.get_value(iter, 0)
        propval = unicode(getattr(obj, prop))
        if propval.find(key) >= 0:
            return False
        return True

    def _findobj(self, obj, colidx=0):
        iter = self._model.get_iter_first()
        while iter:
            val = self._model.get_value(iter, colidx)
            if val == obj:
                return iter
            iter = self._model.iter_next(iter)

    def _signal_obj_changed(self, obj, colidx=0):
        iter = self._findobj(obj, colidx=colidx)
        assert iter
        _logger.debug("signaling change of %r", iter) 
        self._model.row_changed(self._model.get_path(iter), iter)

    def _render_objtext(self, col, cell, model, iter):
        obj = model.get_value(iter, 0)
        cell.set_property('text', unicode(repr(obj)))

    def append_obj(self, obj, **kwargs):
        self._liststore.append((obj,))

    def __onclick(self, path, col, rel_x, rel_y):
        iter = self._model.get_iter(path)
        return self._onclick_full(iter, path, col, rel_x, rel_y)

    def _onclick_full(self, iter, path, col, rel_x, rel_y):
        return self._onclick_iter(iter)

    def _onclick_iter(self, iter):
        obj = self._model.get_value(iter, 0)
        self.__launch_inspector(obj)

    def _get_menuitems(self, obj):
        return []

    # Like GtkTreeView.get_path_at_pos, but excludes headers
    def _get_path_at_pos_no_headers(self, x, y):
        potential_path = self._table.get_path_at_pos(x, y)
        if potential_path is None:
            return None
        return potential_path
    
    def __on_inspect_activate(self, menuitem, o):
        self.__launch_inspector(o)
        
    def __launch_inspector(self, o):
        from hotwire_ui.oinspect import InspectWindow
        from hotwire_ui.shell import locate_current_window        
        w = InspectWindow(o, parent=locate_current_window(self._table))
        w.show_all()
    
    def __get_object_menuitems(self, iter):
        obj = self._model.get_value(iter, 0)        
        menuitem = gtk.ImageMenuItem(_('Inspect Object'))
        menuitem.set_property('image', gtk.image_new_from_stock('gtk-info', gtk.ICON_SIZE_MENU))
        menuitem.connect('activate', self.__on_inspect_activate, obj)
        return [menuitem]

    def __on_button_press(self, table, e):
        potential_path = self._get_path_at_pos_no_headers(int(e.x), int(e.y))
        if potential_path is None:
            return False
        _logger.debug("potential path is %s", potential_path)
        (path, col, rel_x, rel_y) = potential_path        
        if e.button > 1:
            iter = self._model.get_iter(path)
            menu = gtk.Menu()
            have_menuitems = False
            for menuitem in self.__get_func_menuitems(iter):
                menu.append(menuitem)
                have_menuitems = True
            for menuitem in self._get_menuitems(iter):
                menu.append(menuitem)
                have_menuitems = True
            if have_menuitems:
                menu.append(gtk.SeparatorMenuItem())
            for menuitem in self.__get_object_menuitems(iter):
                menu.append(menuitem)
            menu.show_all()
            menu.popup(None, None, None, e.button, e.time)
            return True

        return False
    
    def __on_row_activated(self, tv, path, vc):
        iter = self._model.get_iter(path)        
        self._onclick_iter(iter)
        from hotwire_ui.shell import locate_current_shell
        hw = locate_current_shell(self._table)
        hw.grab_focus()
        
    def start_search(self):
        if not self._table.get_enable_search():
            _logger.debug("search not enabled")            
            raise NotImplementedError()
        _logger.debug("starting search")
        self._table.grab_focus()         
        self._table.emit('start-interactive-search')
        return True
        
class DefaultObjectsRenderer(TreeObjectsRenderer):
    pass

import hotwire_ui.renderers.file
import hotwire_ui.renderers.dict
import hotwire_ui.renderers.filestringmatch
import hotwire_ui.renderers.help
import hotwire_ui.renderers.list
import hotwire_ui.renderers.ps
import hotwire_ui.renderers.unicode
#moddir = hotwire.ModuleDir(os.path.join(os.path.dirname(hotwire.__file__), 'renderers'))
#moddir.do_import()
