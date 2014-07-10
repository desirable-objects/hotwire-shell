# This file is part of the Hotwire Shell user interface.
#   
# Copyright (C) 2007,2008 Colin Walters <walters@verbum.org>
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

import os, sys, logging, StringIO, traceback, inspect, locale

import cairo, gtk, gobject, pango

from hotwire.util import ellipsize
import hotwire_ui.widgets as hotwidgets
from hotwire.logutil import log_except
from hotwire_ui.pixbufcache import PixbufCache

_logger = logging.getLogger("hotwire.ui.OInspect")

def _render_member_icon(member, cell):
    pbcache = PixbufCache.getInstance()
    if inspect.ismethod(member) or inspect.ismethoddescriptor(member):
        pbname = 'dfeet-method.png'
    elif inspect.isdatadescriptor(member) or (hasattr(inspect, 'ismemberdescriptor') and inspect.ismemberdescriptor(member)):
        pbname = 'dfeet-property.png'
    else:
        pbname = 'dfeet-object.png'
    pixbuf = pbcache.get(pbname, size=16, trystock=True, stocksize=gtk.ICON_SIZE_MENU)             
    cell.set_property('pixbuf', pixbuf)

class ObjectInspectLink(hotwidgets.Link):
    def __init__(self):
        super(ObjectInspectLink, self).__init__()
        self.__tips = gtk.Tooltips()
        self.__nameonly = False
        self.__o = None
        self.connect('clicked', self.__on_clicked)
        
    def set_object(self, o, nameonly=False):
        self.__o = o
        self.__nameonly = nameonly
        if o is None:
            self.set_text('')
            self.__tips.set_tip(self, '')
            return
        
        fullname = '%s.%s' % (o.__module__, o.__name__)
        if nameonly:
            text = o.__name__
        else:
            text = fullname
        self.set_text(text)
        self.__tips.set_tip(self, fullname)
    
    @log_except(_logger)
    def __on_clicked(self, s2):
        inspect = InspectWindow(self.__o, parent=self.get_toplevel())
        inspect.show_all() 
        
class ClassInspectorSidebar(gtk.VBox):
    def __init__(self):
        super(ClassInspectorSidebar, self).__init__()
        self.__tooltips = gtk.Tooltips()        
        self.__otype = None
        self.__olabel = ObjectInspectLink()
        self.__olabel.set_ellipsize(True)
        self.pack_start(self.__olabel, expand=False)
        membersframe = gtk.Frame(_('Members'))
        vbox = gtk.VBox()
        membersframe.add(vbox)
        self.__hidden_check = gtk.CheckButton(_('Show _Hidden'))
        vbox.pack_start(self.__hidden_check, expand=False)
        self.__hidden_check.connect_after('toggled', self.__on_show_hidden_toggled)
        self.__members_model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)        
        self.__membersview = gtk.TreeView(self.__members_model)
        self.__membersview.connect('row-activated', self.__on_row_activated)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.add(self.__membersview)
        vbox.add(scroll)
        self.pack_start(membersframe, expand=True)
        colidx = self.__membersview.insert_column_with_data_func(-1, '',
                                                                 gtk.CellRendererPixbuf(),
                                                                 self.__render_icon)
        col = self.__membersview.insert_column_with_attributes(-1, _('Name'),
                                                               hotwidgets.CellRendererText(),
                                                               text=0)
        self.__membersview.set_search_column(0)
        col.set_spacing(0)
        col.set_resizable(True)
        
    def set_otype(self, typeobj):
        if self.__otype == typeobj:
            return
        self.__otype = typeobj
        self.__olabel.set_object(typeobj)  
        self.__set_members()
            
    def __set_members(self):
        showhidden = self.__hidden_check.get_property('active')
        self.__members_model.clear()
        if self.__otype is None:
            return
        for name,member in sorted(inspect.getmembers(self.__otype), lambda a,b: locale.strcoll(a[0],b[0])):
            if not showhidden and name.startswith('_'):
                continue
            self.__members_model.append((name, member))
            
    def __on_show_hidden_toggled(self, *args):
        self.__set_members()
        
    def __render_icon(self, col, cell, model, iter):
        member = model.get_value(iter, 1)
        _render_member_icon(member, cell)
        
    def __on_oclass_clicked(self, *args):
        _logger.debug("inspecting oclass")
        inspect = InspectWindow(self.__otype, parent=self.get_toplevel())
        inspect.show_all()
        
    def __on_row_activated(self, tv, path, vc):
        _logger.debug("row activated: %s", path)
        model = self.__membersview.get_model()
        iter = model.get_iter(path)
        inspect = InspectWindow(model.get_value(iter, 1), parent=self.get_toplevel())
        inspect.show_all()

class InspectWindow(gtk.Window):
    def __init__(self, obj, parent=None):
        gtk.Window.__init__(self, type=gtk.WINDOW_TOPLEVEL)
        
        self.__obj = None
        
        vbox = gtk.VBox()
        self.add(vbox)
        self.__ui_string = """
<ui>
  <menubar name='Menubar'>
    <menu action='FileMenu'>
      <menuitem action='Close'/>
    </menu>
  </menubar>
</ui>
"""
        self.__create_ui()
        vbox.pack_start(self._ui.get_widget('/Menubar'), expand=False)

        contentvbox = gtk.VBox()
        vbox.pack_start(contentvbox, expand=True)
        
        self.__orepr = gtk.Label()
        self.__orepr.set_alignment(0.0, 0.5)
        self.__oclass = gtk.Label()
        self.__oclass.set_alignment(0.0, 0.5)
        contentvbox.pack_start(self.__orepr, expand=False)
        contentvbox.pack_start(self.__oclass, expand=False)
        
        hbox = gtk.HBox()
        self.__definedin_label = gtk.Label()
        self.__definedin_label.set_markup('<b>%s</b>' % (_("Defined in: "),))
        hbox.pack_start(self.__definedin_label, expand=False)
        self.__definedin = hotwidgets.Link()
        self.__definedin.set_alignment(0.0, 0.5)
        self.__definedin.set_ellipsize(True)
        self.__definedin.connect('clicked', self.__on_definedin_clicked)
        hbox.pack_start(self.__definedin, expand=True)
        contentvbox.pack_start(hbox, expand=False)        
        
        metavbox = gtk.VBox()
        contentvbox.add(metavbox)
        metavbox.set_spacing(4)
        docframe = gtk.Frame(_('Docstring'))
        self.__doctext = gtk.TextView()
        self.__doctext.set_editable(False)        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(self.__doctext)        
        docframe.add(scroll)
        metavbox.pack_start(docframe, expand=True)
        
        membersframe = gtk.Frame(_('Members'))
        vbox = gtk.VBox()
        membersframe.add(vbox)        
        self.__hidden_check = gtk.CheckButton(_('Show _Hidden'))
        vbox.pack_start(self.__hidden_check, expand=False)
        self.__hidden_check.connect_after('toggled', self.__on_show_hidden_toggled)
        self.__members_model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)        
        self.__membersview = gtk.TreeView(self.__members_model)
        self.__membersview.connect('row-activated', self.__on_row_activated)        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(self.__membersview)
        vbox.add(scroll)
        metavbox.pack_start(membersframe, expand=True)
        colidx = self.__membersview.insert_column_with_data_func(-1, '',
                                                                 gtk.CellRendererPixbuf(),
                                                                 self.__render_icon)        
        colidx = self.__membersview.insert_column_with_attributes(-1, _('Name'),
                                                                  hotwidgets.CellRendererText(),
                                                                  text=0)
        colidx = self.__membersview.insert_column_with_data_func(-1, _('Member'),
                                                                 hotwidgets.CellRendererText(),
                                                                 self.__render_member)
        self.__membersview.set_search_column(0)
        col = self.__membersview.get_column(colidx-1)
        col.set_spacing(0)
        col.set_resizable(True)

        if parent:
            self.set_transient_for(parent)
        self.set_focus(self.__membersview)
        self.set_title(_('Object inspect: %s - Hotwire')  % (ellipsize(repr(obj), 30),))
        self.set_size_request(640, 480)
        
        self.__set_object(obj)
        
    def __set_object(self, obj):
        self.__obj = obj
        self.__orepr.set_markup(_('<b>Object</b>: %s')  % (gobject.markup_escape_text(repr(obj),)))
        self.__oclass.set_markup(_('<b>Type</b>: %s') % (gobject.markup_escape_text(repr(type(obj))),))
        
        try:
            if isinstance(obj, type):
                osrc_target = obj 
            else:
                osrc_target = type(obj)
            srcpath = inspect.getsourcefile(osrc_target)                
        except TypeError, e:
            _logger.debug("failed to get sourcefile", exc_info=True)
            srcpath = None
        if srcpath:
            self.__definedin.set_text(srcpath)
        
        doc = inspect.getdoc(obj)
        if doc:
            self.__doctext.get_buffer().set_text(doc)
        else:
            self.__doctext.get_buffer().insert_at_cursor(_('(Not documented)'))
        self.__set_members()
            
    def __set_members(self):
        showhidden = self.__hidden_check.get_property('active')
        self.__members_model.clear()
        for name,member in sorted(inspect.getmembers(self.__obj), lambda a,b: locale.strcoll(a[0],b[0])):
            if not showhidden and name.startswith('_'):
                continue
            self.__members_model.append((name, member))
            
    def __on_show_hidden_toggled(self, *args):
        self.__set_members()
            
    def __on_definedin_clicked(self, *args):
        from hotwire.command import Pipeline
        pl = Pipeline.create(None, None, 'edit', self.__definedin.get_text())
        pl.execute_sync()
        
    def __render_icon(self, col, cell, model, iter):
        member = model.get_value(iter, 1)
        _render_member_icon(member, cell)        
            
    def __render_member(self, col, cell, model, iter):
        member = model.get_value(iter, 1)
        cell.set_property('text', repr(member))
        
    def __on_row_activated(self, tv, path, vc):
        _logger.debug("row activated: %s", path)
        model = self.__membersview.get_model()
        iter = model.get_iter(path)
        inspect = InspectWindow(model.get_value(iter, 1), parent=self)
        inspect.show_all()

    def __close_cb(self, action):
        self.__handle_close()

    def __handle_close(self):
        _logger.debug("got close")
        self.destroy()

    def __create_ui(self):
        self.__actiongroup = ag = gtk.ActionGroup('WindowActions')
        actions = [
            ('FileMenu', None, _('_File')),
            ('Close', gtk.STOCK_CLOSE, _('_Close'), '<control>Return', _('Hide window'), self.__close_cb),
            ]
        ag.add_actions(actions)
        self._ui = gtk.UIManager()
        self._ui.insert_action_group(ag, 0)
        self._ui.add_ui_from_string(self.__ui_string)
        self.add_accel_group(self._ui.get_accel_group())
