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

import os, sys, re, logging, string,locale

import gtk, gobject, pango

from hotwire.state import Preferences
from hotwire.logutil import log_except
import hotwire_ui.widgets as hotwidgets
from hotwire_ui.pixbufcache import PixbufCache
from hotwire_ui.adaptors.editors import EditorRegistry,Editor
from hotwire.externals.dispatch import dispatcher

_logger = logging.getLogger("hotwire.ui.Preferences")
            
class PrefEditorCombo(gtk.ComboBox):
    def __init__(self):
        super(PrefEditorCombo, self).__init__(model=gtk.ListStore(gobject.TYPE_PYOBJECT))
        
        editors = EditorRegistry.getInstance()    
        self.__hotwire_editor = editors['c5851b9c-2618-4078-8905-13bf76f0a94f']
        self.__reload_editors()
        self.set_row_separator_func(self.__is_row_separator)
        cell = gtk.CellRendererPixbuf()
        self.pack_start(cell, expand=False)
        self.set_cell_data_func(cell, self.__render_editor_icon)
        cell = hotwidgets.CellRendererText()
        self.pack_start(cell)
        self.set_cell_data_func(cell, self.__render_editor_name)
        
        dispatcher.connect(self.__reload_editors, sender=editors)
        
        self.select_editor_uuid(editors.get_preferred().uuid)
        self.connect('changed', self.__on_changed)
        
    def __on_changed(self, combo):
        active = self.get_active_iter()
        editor = self.get_model().get_value(active, 0)
        editors = EditorRegistry.getInstance()
        editors.set_preferred(editor)

    def select_editor_uuid(self, uuid):
        for row in self.get_model():
            val = row[0]
            if val is None: 
                continue
            if val.uuid is uuid:
                self.set_active_iter(row.iter)
                return        
        raise KeyError("Can't find uuid %r" % (uuid,))
        
    def __is_row_separator(self, model, iter):
        v = model.get_value(iter, 0)
        return v is None
        
    @log_except(_logger)
    def __reload_editors(self, *args, **kwargs):
        editors = EditorRegistry.getInstance()
        editors = list(editors)
        model = self.get_model() 
        model.clear()
        builtin_editors = [self.__hotwire_editor]
        for e in builtin_editors:
            model.append((e,))
        model.append((None,))
        for e in sorted(editors, lambda a,b: locale.strcoll(a.name, b.name)):
            if e in builtin_editors:
                continue
            model.append((e,))
        
    def __render_editor_icon(self, celllayout, cell, model, iter):
        e = model.get_value(iter, 0)
        if e is None: return        
        if e.icon is None:
            cell.set_property('pixbuf', None)
        else:
            pbcache = PixbufCache.getInstance()
            # Right now use 16 since that's favicon size
            pixbuf = pbcache.get(e.icon, size=16, trystock=True, stocksize=gtk.ICON_SIZE_MENU)
            cell.set_property('pixbuf', pixbuf)      
        
    def __render_editor_name(self, celllayout, cell, model, iter):
        e = model.get_value(iter, 0)
        if e is None: return        
        cell.set_property('text', e.name)
            
class PrefsWindow(gtk.Dialog):
    def __add_checkbutton(self, name, prefname, function, vbox):
        prefs = Preferences.getInstance()
        checkbutton = gtk.CheckButton(name)
        checkbutton.set_property('active', prefs.get_pref(prefname, default=True))
        checkbutton.connect('toggled', function)        
        vbox.pack_start(hotwidgets.Align(checkbutton, padding_left=12), expand=False)

    def __init__(self):
        super(PrefsWindow, self).__init__(title=_('Preferences'),
                                          parent=None,
                                          flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                          buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_ACCEPT))
        
        prefs = Preferences.getInstance()
        
        self.connect('response', lambda *args: self.hide())
        self.connect('delete-event', self.hide_on_delete)
                
        self.set_has_separator(False)
        self.set_border_width(5)
        
        self.__vbox = gtk.VBox()
        self.vbox.add(self.__vbox)   
        self.vbox.set_spacing(2)
        self.__notebook = gtk.Notebook()
        self.__vbox.add(self.__notebook)

        self.__general_tab = gtk.VBox()
        self.__notebook.append_page(self.__general_tab)
        self.__notebook.set_tab_label_text(self.__general_tab, _('General'))
        
        vbox = gtk.VBox()
        vbox.set_border_width(12)
        vbox.set_spacing(6)
        self.__general_tab.pack_start(vbox, expand=False)                           
        label = gtk.Label()
        label.set_markup('<b>%s</b>' % (_('Interface'),))
        label.set_alignment(0.0, 0.0)
        vbox.pack_start(hotwidgets.Align(label), expand=False)
        menuaccess = gtk.CheckButton(_('Disable menu access keys'))
        menuaccess.set_property('active', not prefs.get_pref('ui.menuaccels', default=True))
        menuaccess.connect('toggled', self.__on_menuaccess_toggled)        
        vbox.pack_start(hotwidgets.Align(menuaccess, padding_left=12), expand=False)
        readline = self.__readline = gtk.CheckButton(_('Enable Unix "Readline" keys (Ctrl-A, Alt-F, Ctrl-K, etc.)'))
        readline.set_property('active', prefs.get_pref('ui.emacs', default=False))
        readline.connect('toggled', self.__on_readline_toggled)        
        vbox.pack_start(hotwidgets.Align(readline, padding_left=12), expand=False)
        self.__sync_emacs_sensitive()
        
        label = gtk.Label()
        label.set_markup('<b>%s</b>' % (_('System'),))
        label.set_alignment(0.0, 0.0)
        vbox.pack_start(hotwidgets.Align(label), expand=False)
        hbox = gtk.HBox()
        vbox.pack_start(hotwidgets.Align(hbox, padding_left=12), expand=False)
        ed_label = gtk.Label(_('Editor: '))
        hbox.pack_start(ed_label, expand=False)
        self.__ed_combo = PrefEditorCombo()
        hbox.pack_start(self.__ed_combo, expand=False)        
        
        self.__term_tab = gtk.VBox()
        self.__notebook.append_page(self.__term_tab)
        self.__notebook.set_tab_label_text(self.__term_tab, _('Terminal'))   
        
        vbox = gtk.VBox()
        vbox.set_border_width(12)
        vbox.set_spacing(6) 
        label = gtk.Label()
        label.set_markup('<b>%s</b>' % (_('Interface'),))
        label.set_alignment(0.0, 0.0)
        vbox.pack_start(label, expand=False)
        self.__term_tab.pack_start(vbox, expand=False)
        
        hbox = gtk.HBox()
        vbox.pack_start(hotwidgets.Align(hbox, padding_left=12), expand=False)
        sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        fg_label = gtk.Label(_('Foreground Color: '))
        sg.add_widget(fg_label)
        hbox.pack_start(fg_label, expand=False)
        fg_color = self.__fg_color = gtk.ColorButton(gtk.gdk.color_parse(prefs.get_pref('term.foreground', default='#000')))
        hbox.pack_start(fg_color, expand=False)
        fg_color.connect('color-set', self.__on_fg_bg_changed)
        
        hbox = gtk.HBox()
        vbox.pack_start(hotwidgets.Align(hbox, padding_left=12), expand=False)
        bg_label = gtk.Label(_('Background Color: '))
        sg.add_widget(bg_label)
        hbox.pack_start(bg_label, expand=False)
        bg_color = self.__bg_color = gtk.ColorButton(gtk.gdk.color_parse(prefs.get_pref('term.background', default='#FFF')))
        hbox.pack_start(bg_color, expand=False)
        bg_color.connect('color-set', self.__on_fg_bg_changed)

        self.__folders_tab = gtk.VBox()
        self.__notebook.append_page(self.__folders_tab)
        self.__notebook.set_tab_label_text(self.__folders_tab, _('Folders'))   

        vbox = gtk.VBox()
        vbox.set_border_width(12)
        vbox.set_spacing(6) 
        label = gtk.Label()
        label.set_markup('<b>%s</b>' % (_('Default view'),))
        label.set_alignment(0.0, 0.0)
        vbox.pack_start(label, expand=False)
        self.__folders_tab.pack_start(vbox, expand=False)
        self.__add_checkbutton(_('Sort folders before files'), 'hotwire.ui.render.File.general.foldersbeforefiles', 
                               self.__on_folders_before_files_toggled, vbox)

        vbox = gtk.VBox()
        vbox.set_border_width(12)
        vbox.set_spacing(6) 
        label = gtk.Label()
        label.set_markup('<b>%s</b>' % (_('List columns'),))
        label.set_alignment(0.0, 0.0)
        vbox.pack_start(label, expand=False)
        self.__folders_tab.pack_start(vbox, expand=False)

        self.__add_checkbutton(_('Size'), 'hotwire.ui.render.File.columns.size', self.__on_list_size_toggled, vbox)
        self.__add_checkbutton(_('Last modified'), 'hotwire.ui.render.File.columns.last_modified', self.__on_list_lastmodified_toggled, vbox)
        self.__add_checkbutton(_('Owner'), 'hotwire.ui.render.File.columns.owner', self.__on_list_owner_toggled, vbox)
        self.__add_checkbutton(_('Group'), 'hotwire.ui.render.File.columns.group', self.__on_list_group_toggled, vbox)
        self.__add_checkbutton(_('Permissions'), 'hotwire.ui.render.File.columns.permissions', self.__on_list_permissions_toggled, vbox)
        self.__add_checkbutton(_('File type'), 'hotwire.ui.render.File.columns.mime', self.__on_list_filetype_toggled, vbox)
        
    def __on_fg_bg_changed(self, cb):
        prefs = Preferences.getInstance()        
        def sync_color_pref(button, prefname):
            color = button.get_color()
            color_str = '#%04X%04X%04X' % (color.red, color.green, color.blue)
            prefs.set_pref(prefname, color_str)
        sync_color_pref(self.__fg_color, 'term.foreground')
        sync_color_pref(self.__bg_color, 'term.background')
        
    def __sync_emacs_sensitive(self):
        prefs = Preferences.getInstance()
        accels = prefs.get_pref('ui.menuaccels', default=True)
        if accels and prefs.get_pref('ui.emacs', default=False): 
            prefs.set_pref('ui.emacs', False)  
            self.__readline.set_property('active', False)
        self.__readline.set_sensitive(not accels)                  
        
    def __on_menuaccess_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('ui.menuaccels', not active)
        self.__sync_emacs_sensitive()

    def __on_folders_before_files_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('hotwire.ui.render.File.general.foldersbeforefiles', active)

    def __on_list_name_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('hotwire.ui.render.File.columns.name', active)

    def __on_list_size_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('hotwire.ui.render.File.columns.size', active)

    def __on_list_lastmodified_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('hotwire.ui.render.File.columns.last_modified', active)

    def __on_list_owner_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('hotwire.ui.render.File.columns.owner', active)

    def __on_list_group_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('hotwire.ui.render.File.columns.group', active)

    def __on_list_permissions_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('hotwire.ui.render.File.columns.permissions', active)

    def __on_list_filetype_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('hotwire.ui.render.File.columns.mime', active)
        
    def __on_readline_toggled(self, cb):
        active = cb.get_property('active')
        prefs = Preferences.getInstance()
        prefs.set_pref('ui.emacs', active)   
