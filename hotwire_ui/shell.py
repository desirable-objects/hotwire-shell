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

import os, sys, re, logging, string, locale, weakref

import gtk, gobject, pango

from hotwire.command import PipelineFactory,Pipeline,Command,HotwireContext
from hotwire.command import PipelineLanguageRegistry,BaseCommandResolver
from hotwire.completion import Completion, VerbCompleter, TokenCompleter
import hotwire.command
import hotwire.version
from hotwire_ui.pixbufcache import PixbufCache
import hotwire_ui.widgets as hotwidgets
import hotwire_ui.pyshell
from hotwire.externals.singletonmixin import Singleton
from hotwire.sysdep.term import Terminal
from hotwire.builtin import BuiltinRegistry
from hotwire.cmdalias import Alias, AliasRegistry
from hotwire.gutil import *
from hotwire.util import markup_for_match, quote_arg
from hotwire.fs import path_unexpanduser, path_expanduser, unix_basename, path_fromurl
from hotwire.sysdep import is_unix
from hotwire.sysdep.fs import File, Filesystem
from hotwire.state import History, Preferences, ViewState
from hotwire_ui.command import CommandExecutionDisplay,CommandExecutionControl
from hotwire_ui.completion import CompletionStatusDisplay
from hotwire_ui.aboutdialog import HotwireAboutDialog
from hotwire_ui.msgarea import MsgArea,MsgAreaController
from hotwire_ui.quickfind import QuickFindWindow
from hotwire_ui.prefs import PrefsWindow
from hotwire_ui.dirswitch import DirSwitchWindow
from hotwire.logutil import log_except
from hotwire.externals.dispatch import dispatcher
from hotwire_ui.navigationbar import NavigationBar

_logger = logging.getLogger("hotwire.ui.Shell")

def locate_current_window(widget):
    """A function which can be called from any internal widget to gain a reference
    to the toplevel Hotwire window container."""
    win = widget.get_toplevel()
    return win

def locate_current_shell(widget):
    """A function which can be called from any internal widget to gain a reference
    to the toplevel Hotwire instance."""
    win = locate_current_window(widget)
    return win.get_current_widget()

class HotwireClientContext(hotwire.command.HotwireContext):
    def __init__(self, hotwire, **kwargs):
        super(HotwireClientContext, self).__init__(**kwargs)
        self.__hotwire = hotwire
        self.history = None

    def do_cd(self, dpath):
        self.__hotwire.internal_execute('cd', dpath)
        
    def get_gtk_event_time(self):
        return gtk.get_current_event_time()

    def push_error(self, text, **kwargs):
        self.__hotwire.push_error(text, **kwargs)

    def push_msg(self, text, **kwargs):
        self.__hotwire.push_msg(text, **kwargs)

    def get_current_output_metadata(self):
        return self.__hotwire.get_current_output_metadata()
    
    def get_current_output_ref(self):
        return self.__hotwire.get_current_output_ref()
    
    def snapshot_output(self, ref):
        return self.__hotwire.snapshot_output(ref)
    
    def snapshot_selected_output(self, ref):
        return self.__hotwire.snapshot_selected_output(ref) 

    def get_history(self):
        # FIXME arbitrary limit
        return self.history.search_commands(None, None, limit=250)

    def ssh(self, host):
        self.__hotwire.ssh(host)

    def remote_exit(self):
        self.__hotwire.remote_exit()

    def open_term(self, cwd, pipeline, arg, window=False, autoclose=False):
        gobject.idle_add(self.__idle_open_term, cwd, pipeline, arg, window, autoclose)

    def __idle_open_term(self, cwd, pipeline, arg, do_window, autoclose):
        title = str(pipeline)
        window = locate_current_window(self.__hotwire)
        term = Terminal.getInstance().get_terminal_widget_cmd(cwd, arg, title, autoclose=autoclose)
        if do_window:
            window.new_win_widget(term, title)
        else:
            window.new_tab_widget(term, title)
        
    def get_ui(self):
        return self.__hotwire.get_global_ui()
    
class LanguageSwitchWindow(QuickFindWindow):
    def __init__(self):
        self.__langs = PipelineLanguageRegistry.getInstance()
        self.__ordered_langs = []
        self.__reload_languages()
        dispatcher.connect(self.__reload_languages, sender=self.__langs)        
        super(LanguageSwitchWindow, self).__init__(_('Switch Input Language'))
        
    def __reload_languages(self,):
        self.__ordered_langs = list(self.__langs.iter_sorted())

    def _do_search(self, text):
        text_lower = text.lower()
        for lang in self.__ordered_langs:
            name = lang.langname
            name_lower = name.lower()
            markup = self._markup_search(name, text, name_lower, text_lower)
            if markup is not None:      
                yield (lang, markup, lang.icon)              
        
class PipelineLanguageButton(gtk.Button):
    __gproperties__ = { 
                       'lang' : (gobject.TYPE_PYOBJECT, '', '', gobject.PARAM_READWRITE)
                      }    
    def __init__(self):
        super(PipelineLanguageButton, self).__init__()
        self.__tooltips = gtk.Tooltips()
        self.__image = gtk.Image()
        self.set_property('image', self.__image)
        
        self.set_focus_on_click(False)
        langs = PipelineLanguageRegistry.getInstance()        
        self.__curlang = langs['62270c40-a94a-44dd-aaa0-689f882acf34']
        self.connect('clicked', self.__on_clicked)
        
    def __on_clicked(self, *args):
        win = LanguageSwitchWindow()
        lang = win.run_get_value()
        win.destroy()
        if lang is not None:
            self.set_lang(lang)
        
    def __sync_icon(self,):
        lang = self.__curlang       
        if lang.icon is None:
            self.__image.set_property('pixbuf', None)
        else:
            pbcache = PixbufCache.getInstance()
            # Right now use 16 since that's favicon size
            pixbuf = pbcache.get(lang.icon, size=16, trystock=True, stocksize=gtk.ICON_SIZE_MENU)
            self.__image.set_property('pixbuf', pixbuf)
        self.__tooltips.set_tip(self, _('Input language: %s') % (lang.langname,))     
        
    def do_get_property(self, property):
        if property.name == 'lang':
            return self.get_lang()
        else:
            raise AttributeError('unknown property %s' % property.name)        
        
    def set_lang(self, lang):
        assert lang is not None
        self.__curlang = lang
        self.__sync_icon()
        self.notify('lang')
            
    def get_lang(self):
        return self.__curlang

class ShellCommandResolver(BaseCommandResolver):
    """Expands Alias objects in addition to File."""
    def __init__(self):
        super(ShellCommandResolver, self).__init__()
        
    def _resolve_verb_completion(self, text, completion):
        target = completion.target
        if isinstance(target, Alias) and text == target.name:
            return True
        return super(ShellCommandResolver, self)._resolve_verb_completion(text, completion)
        
    def _expand_verb_completion(self, completion):
        if isinstance(completion.target, Alias):
            tokens = list(Pipeline.tokenize(completion.target.target, internal=True))                   
            return (BuiltinRegistry.getInstance()[tokens[0].text], tokens[1:])
        return super(ShellCommandResolver, self)._expand_verb_completion(completion)
        
class CwdSelectorWindow(gtk.Dialog):
    def __init__(self, parent, model):
        super(CwdSelectorWindow, self).__init__(title=_('Switch Recent Directory'),
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
        
        self.__scroll = gtk.ScrolledWindow()
        self.__scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.__results = gtk.TreeView(model)
        self.__results.connect('row-activated', self.__on_row_activated)
        self.__scroll.add(self.__results)
        colidx = self.__results.insert_column_with_data_func(-1, '',
                                                             gtk.CellRendererPixbuf(),
                                                             self.__render_icon)
        colidx = self.__results.insert_column_with_data_func(-1, '',
                                                             hotwidgets.CellRendererText(ellipsize=True),
                                                             self.__render_directory)        
        self.__vbox.pack_start(hotwidgets.Border(self.__scroll), expand=True)
        self.__selection = self.__results.get_selection()
        self.__selection.set_mode(gtk.SELECTION_SINGLE)
        self.__results.set_headers_visible(False)
        self.__results.grab_focus()
        
    def __on_row_activated(self, *args):
        self.response(gtk.RESPONSE_ACCEPT)
        
    def __render_icon(self, col, cell, model, iter):
        cell.set_property('icon-name', gtk.STOCK_DIRECTORY)
        
    def __render_directory(self, col, cell, model, iter):
        value = model.get_value(iter, 0)   
        cell.set_property('text', value)
        
    def get_selection(self):
        return self.__selection
        
class CwdDisplay(gtk.Button):
    __gsignals__ = {
        "changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, []),
    }
    def __init__(self):
        super(CwdDisplay, self).__init__()
        self.set_use_underline(False)
        self.set_relief(gtk.RELIEF_NONE)
        self.set_focus_on_click(False)
        self.__tooltips = gtk.Tooltips()
        
        self.__home = os.path.expanduser('~')  
                
        self.__image = gtk.Image()
        self.__image.set_from_stock(gtk.STOCK_DIRECTORY, gtk.ICON_SIZE_MENU)
        self.set_property('image', self.__image)
        self.__model = gtk.ListStore(gobject.TYPE_STRING)
        self.__selector_window = CwdSelectorWindow(None, self.__model)
        self.connect('clicked', self.__on_clicked)
        self.__sync_label()
        
    def __sync_label(self): 
        active = self.get_active_iter()
        if active is None:
            return
        value = origvalue = self.__model.get_value(active, 0)
        if value is None:
            return
        if value == self.__home:
            value = '~'
        elif value == '/':
            pass
        else:
            value = unix_basename(value)
        # workaround http://bugzilla.gnome.org/show_bug.cgi?id=519429
        value = value.replace('_', '__')
        self.set_label(value)
        label = self.get_child().get_child().get_children()[-1]
        label.set_max_width_chars(50)
        label.set_ellipsize(pango.ELLIPSIZE_END)
        self.__tooltips.set_tip(self, _('Current directory: %s') % (origvalue,))        
        
    def __on_clicked(self, *args):
        self.__selector_window.show_all()
        resp = self.__selector_window.run()
        self.__sync_label()
        if resp == gtk.RESPONSE_ACCEPT:
            self.emit('changed')
            
    def set_active(self, idx):
        self.__selector_window.get_selection().select_path((idx,))
        self.__sync_label()
        
    def set_active_iter(self, iter):
        self.__selector_window.get_selection().select_iter(iter)
        self.__sync_label()
    
    def get_active_iter(self):
        return self.__selector_window.get_selection().get_selected()[1]
    
    def get_model(self):
        return self.__model

class Hotwire(gtk.VBox):
    MAX_RECENTDIR_LEN = 10
    __gsignals__ = {
        "title" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
        "new-tab-widget" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, gobject.TYPE_STRING)),
        "new-window-cmd" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,))        
    }
    MAX_TABHISTORY = 30
    def __init__(self, initcwd=None, window=None, ui=None, initcmd_widget=None, initcmd=None):
        super(Hotwire, self).__init__()

        _logger.debug("Creating Hotwire instance, initcwd=%s", initcwd)

        self.__ui = ui
        
        self.__ui_string = '''
<ui>
  <menubar name='Menubar'>
    <menu action='EditMenu'>
      <placeholder name='EditMenuAdditions'>
        <separator/>
        <menuitem action='SwitchLanguage'/>
        <separator/>
      </placeholder>
    </menu>
    <menu action='ViewMenu'>
      <placeholder name='ViewMenuAdditions'>
        <menuitem action='NavigationBar'/>
        <separator/>
      </placeholder>
    </menu>
    <placeholder name='WidgetMenuAdditions'>  
      <menu action='GoMenu'>
        <menuitem action='Up'/>
        <menuitem action='Back'/>
        <menuitem action='Forward'/>
        <separator/>
        <menuitem action='DirSwitch'/>
        <separator/>
        <menuitem action='AddBookmark'/>
        <separator/>
        <menuitem action='Home'/>
      </menu>
    </placeholder>
  </menubar>
</ui>'''
        self.__actions = [
            ('SwitchLanguage', 'hotwire', _('Switch _Language'), '<control><shift>L', _('Change the input language'), self.__on_switch_language_cb),
            ('GoMenu', None, _('_Go')),
            ('Up', 'gtk-go-up', _('Up'), '<alt>Up', _('Go to parent directory'), self.__up_cb),
            ('Back', 'gtk-go-back', _('Back'), '<alt>Left', _('Go to previous directory'), self.__back_cb),
            ('Forward', 'gtk-go-forward', _('Forward'), '<alt>Right', _('Go to next directory'), self.__forward_cb),
            ('AddBookmark', None, _('Add Bookmark'), '<alt><shift>B', _('Set a bookmark at this directory'), self.__add_bookmark_cb),
            ('Home', 'gtk-home', _('_Home'), '<alt>Home', _('Go to home directory'), self.__home_cb),
            ('DirSwitch', 'gtk-find', _('Quick Switch'), '<alt>Down', _('Search for a directory'), self.__dirswitch_cb)
        ]
        self.__toggle_actions = [
            ('NavigationBar', None, _('_Navigation Bar'), None, _('Toggle display of navigation bar'), self.__navbar_cb)
        ]
        self.__action_group = gtk.ActionGroup('HotwireActions')
        self.__action_group.add_actions(self.__actions)
        self.__action_group.add_toggle_actions(self.__toggle_actions)

        self.context = HotwireClientContext(self, initcwd=initcwd)
        self.context.history = History.getInstance()
        self.__tabhistory = []
        dispatcher.connect(self.__on_cwd, 'cwd', self.context)

        self.__cwd = self.context.get_cwd()
        
        bookmarks = Filesystem.getInstance().get_bookmarks()
        dispatcher.connect(self.__handle_bookmark_change, sender=bookmarks)
        gobject.idle_add(self.__sync_bookmarks)

        self.drag_dest_set(gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP,
                           [('text/uri-list', 0, 0)],
                           gtk.gdk.ACTION_COPY) 
        self.connect("drag-data-received", self.__on_drag_data_received)
        self.connect("key-press-event", self.__on_toplevel_keypress) 

        self.__paned = gtk.VBox()
        self.__topbox = gtk.VBox()
        self.__welcome = gtk.Label('Welcome to Hotwire.')
        self.__welcome_align = hotwidgets.Align(self.__welcome, yscale=1.0, xscale=1.0)
        self.__paned.pack_start(self.__welcome_align, expand=True)
        self.pack_start(self.__paned, expand=True)

        self.__navigation_bar = NavigationBar(self.context)
        # Visibility is synced by __sync_navbar_display
        self.__navigation_bar.show_all()
        self.__navigation_bar.set_no_show_all(True)
        view_state = ViewState.getInstance()
        navigation_bar_show = view_state.get_state('NavigationBar')
        _logger.debug('Show address bar? %s' % navigation_bar_show)
        if navigation_bar_show == None:
            _logger.debug("No NavigationBar record")
            self.__navigation_bar.hide()
            view_state.set_state('NavigationBar', 0)
        elif not navigation_bar_show:
            _logger.debug("Hide NavigationBar")
            self.__navigation_bar.hide()
        else:
            _logger.debug("Show NavigationBar")
            self.__navigation_bar.show()
        
        self.__topbox.pack_start(self.__navigation_bar, expand = False)
        self.__outputs = CommandExecutionControl(self.context)
        self.__outputs.connect("new-window", self.__on_commands_new_window)      
        self.__topbox.pack_start(self.__outputs, expand=True)

        self.__bottom = gtk.VBox()
        self.__paned.pack_end(hotwidgets.Align(self.__bottom, xscale=1.0, yalign=1.0), expand=False)
        
        self.__emacs_bindings = None
        self.__active_input_completers = []
        
        self.__msgarea_control = MsgAreaController()
        self.__bottom.pack_start(self.__msgarea_control, expand=False)
        
        self.__inputline = gtk.HBox()
        
        self.__overview_button = self.__outputs.create_overview_button()
        self.__inputline.pack_start(self.__overview_button, expand=False)
        self.__unseen_button = self.__outputs.create_unseen_button()
        self.__inputline.pack_start(self.__unseen_button, expand=False)
        
        self.__lang_button = PipelineLanguageButton()
        self.__lang_button.set_lang(PipelineLanguageRegistry.getInstance()['62270c40-a94a-44dd-aaa0-689f882acf34'])
        self.__lang_button.connect('notify::lang', self.__on_lang_button_changed)
        self.__inputline.pack_start(self.__lang_button, expand=False) 
        self.__doing_recentdir_sync = False
        self.__doing_recentdir_navigation = False
        
        self.__recentdir_navigation_index = None
        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.__recentdirs = CwdDisplay()
        self.__recentdirs.connect('changed', self.__on_recentdir_selected)
        self.__inputline.pack_start(hotwidgets.Align(self.__recentdirs), expand=False)           
        
        self.__bottom.pack_start(self.__inputline, expand=False)        
        self.__input = gtk.Entry()
        self.__input.connect("notify::scroll-offset", self.__on_scroll_offset)
        self.__input.connect("notify::text", lambda *args: self.__on_input_changed())
        self.__input.connect("key-press-event", lambda i, e: self.__on_input_keypress(e))
        self.__input.connect("focus-out-event", self.__on_entry_focus_lost)
        self.__inputline.pack_start(self.__input, expand=True)

        self.__idle_parse_id = 0
        self.__parse_stale = False
        self.__parse_resolved = None
        self.__parse_partial = None
        self.__resolver = ShellCommandResolver()
        self.__pipeline_factory = PipelineFactory(self.context, self.__resolver)
        self.__parsed_pipeline = None
        self.__langtype = PipelineLanguageRegistry.getInstance()['62270c40-a94a-44dd-aaa0-689f882acf34']
        self.__verb_completer = VerbCompleter()
        self.__token_completer = TokenCompleter()
        self.__completion_active = False
        self.__completion_active_position = False
        self.__completion_chosen = None
        self.__completion_suppress = False
        self.__completion_async_blocking = False
        self.__completions = CompletionStatusDisplay(self.__input, window, context=self.context,
                                                     tabhistory=self.__tabhistory)
        self.__completions.connect('completion-selected', self.__on_completion_selected)
        self.__completions.connect('completions-loaded', self.__on_completions_loaded)
        self.__completions.connect('histitem-selected', self.__on_histitem_selected)
        self.__completion_token = None
        self.__history_suppress = False
        self.__history_search_saved = None
        self.__history_search_active = False

        self.__sync_cwd()
#        self.__sync_navbar_display()
        self.__update_status()

        prefs = Preferences.getInstance()
        prefs.monitor_prefs('ui.', self.__on_pref_changed)
        self.__sync_prefs(prefs)

        if initcmd_widget:
            self.__unset_welcome()            
            self.__outputs.add_cmd_widget(initcmd_widget)
        elif initcmd:
            gobject.idle_add(self.internal_execute_str, initcmd)

    def get_global_ui(self):
        return self.__ui

    def get_ui_pairs(self):
        return [self.__outputs.get_ui(), (self.__ui_string, self.__action_group, self.__init_ui)]

    def __init_ui(self, ui_manager):
        bar = self.__action_group.get_action('NavigationBar')
        view_state = ViewState.getInstance()
        navigation_bar_show = view_state.get_state('NavigationBar')
        #bar = ui_manager.get_widget('/Menubar/ViewMenu/NavigationBar')
        if navigation_bar_show:
            _logger.debug("Activate NavigationBar")
            bar.set_active(True)
        else:
            _logger.debug("Deactivate NavigationBar")
            bar.set_active(False)
    
    def append_tab(self, widget, title):
        self.emit("new-tab-widget", widget, title)

    def __clear_msg(self):
        self.__msgarea_control.clear()

    def push_error(self, msg, secondary=None):
        self.push_msg(msg, secondary=secondary, stockid=gtk.STOCK_DIALOG_ERROR)

    def push_msg(self, msg, secondary=None, stockid=gtk.STOCK_DIALOG_INFO):
        self.__clear_msg()
        if msg is None or msg == '':
            return
        msgarea = self.__msgarea_control.new_from_text_and_icon(stockid, msg, secondary=secondary,
                                                                buttons=[(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)])
        msgarea.connect('response', self.__on_msgarea_response)
        msgarea.show_all()
        
    def __on_msgarea_response(self, msgarea, respid):
        self.__clear_msg()

    def __on_lang_button_changed(self, *args):
        newlang = self.__lang_button.get_lang()
        if newlang == self.__langtype:
            return
        self.__langtype = newlang 
        _logger.debug("input language changed: %r", self.__langtype)
        self.__queue_parse()
        
    def __on_switch_language_cb(self, action):
        self.__lang_button.clicked()
        
    def get_active_lang(self):
        return self.__langtype
            
    def __add_bookmark_cb(self, action):
        bookmarks = Filesystem.getInstance().get_bookmarks()
        bookmarks.add(self.__cwd)
            
    def __handle_bookmark_change(self, signal=None, sender=None):
        self.__sync_bookmarks()
        
    @log_except(_logger)
    def __sync_bookmarks(self):
        gomenu = self.__ui.get_widget('/Menubar/WidgetMenuAdditions/GoMenu/Home').get_parent()
        removals = []
        for child in gomenu:
            if child.get_data('hotwire-dynmenu'):
                removals.append(child)
                
        for removal in removals:
            _logger.debug("removing %r", removal)
            gomenu.remove(removal)
            
        for bookmark in Filesystem.getInstance().get_bookmarks():
            bn = unix_basename(bookmark)
            menuitem = gtk.ImageMenuItem(bn)
            menuitem.set_data('hotwire-dynmenu', True)
            menuitem.set_property('image', gtk.image_new_from_stock('gtk-directory', gtk.ICON_SIZE_MENU))
            menuitem.connect('activate', self.__on_bookmark_activate, bookmark)
            menuitem.show_all()
            gomenu.append(menuitem)
            
    def __on_bookmark_activate(self, menu, bookmark):
        self.internal_execute('cd', bookmark)

    def __sync_cwd(self):
        max_recentdir_len = self.MAX_RECENTDIR_LEN
        model = self.__recentdirs.get_model()
        if self.__doing_recentdir_navigation:
            self.__doing_recentdir_navigation = False
            _logger.debug("in recentdir navigation, setting active iter")
            iter = model.iter_nth_child(None, self.__recentdir_navigation_index)
            self.__doing_recentdir_sync = True            
            self.__recentdirs.set_active_iter(iter)
            self.__doing_recentdir_sync = False
            self.__sync_recentdir_navigation_sensitivity()            
            return
        if model.iter_n_children(None) == max_recentdir_len:
            model.remove(model.iter_nth_child(None, max_recentdir_len-1))
        unexpanded = path_unexpanduser(self.__cwd)
        model.prepend((unexpanded,))
        self.__doing_recentdir_sync = True
        self.__recentdirs.set_active(0)
        self.__doing_recentdir_sync = False
        _logger.debug("added new recentdir")
        if not self.__doing_recentdir_navigation:
            _logger.debug("reset recentdir index")                   
            self.__recentdir_navigation_index = None
        self.__sync_recentdir_navigation_sensitivity()
        self.__navigation_bar.refresh()
        
    def __sync_recentdir_navigation_sensitivity(self):
        idx = self.__recentdir_navigation_index        
        self.__action_group.get_action('Forward').set_sensitive(idx is not None and idx > 0)
        n_total = self.__recentdirs.get_model().iter_n_children(None)
        self.__action_group.get_action('Back').set_sensitive((idx is None and n_total > 1) or (idx is not None and idx < n_total-1))
        bookmarkable = self.__cwd != path_expanduser("~") and self.__cwd not in Filesystem.getInstance().get_bookmarks()
        self.__action_group.get_action('AddBookmark').set_sensitive(bookmarkable)

    def __up_cb(self, action):
        _logger.debug("up")
        self.internal_execute('cd', '..')
        
    @log_except(_logger)
    def __navbar_cb(self, action):
        self.__sync_navbar_display()
    
    def __sync_navbar_display(self):
        active = self.__action_group.get_action('NavigationBar').get_active()
        view_state = ViewState.getInstance()
        bar = self.__navigation_bar
        if active:
            view_state.set_state('NavigationBar', 1)
            bar.show()
        else:
            view_state.set_state('NavigationBar', 0)
            bar.hide()
        
    @log_except(_logger)
    def __dirswitch_cb(self, action):
        _logger.debug("doing dirswitch")
        win = DirSwitchWindow()
        dirpath = win.run_get_value()
        if not dirpath:
            return
        self.internal_execute('cd', dirpath)
        
    def __do_recentdir_cd(self):
        model = self.__recentdirs.get_model()
        iter = model.iter_nth_child(None, self.__recentdir_navigation_index)
        path = path_expanduser(model.get_value(iter, 0))
        self.__doing_recentdir_navigation = True
        self.internal_execute('cd', path)            

    def __back_cb(self, action):
        _logger.debug("back")
        if self.__recentdir_navigation_index is None:
            self.__recentdir_navigation_index = 0
        self.__recentdir_navigation_index += 1
        self.__do_recentdir_cd()        

    def __forward_cb(self, action):
        _logger.debug("forward")
        assert(self.__recentdir_navigation_index is not None)
        self.__recentdir_navigation_index -= 1
        self.__do_recentdir_cd()   

    def __home_cb(self, action):
        _logger.debug("home")
        self.internal_execute('cd')

    def __on_commands_new_window(self, outputs, cmdview):
        _logger.debug("got new window request for %s", cmdview)
        self.emit('new-window-cmd', cmdview)

    @defer_idle_func(timeout=0) # commands can invoke the cwd signal from a thread context
    def __on_cwd_idle(self,cwd):
        self.__cwd = cwd
        self.__sync_cwd()
        self.__update_status()

    def __on_cwd(self, cwd, sender=None):
        ctx = sender
        self.__on_cwd_idle(cwd)

    def __on_recentdir_selected(self, *args):
        if self.__doing_recentdir_sync:
            return
        iter = self.__recentdirs.get_active_iter()
        d = self.__recentdirs.get_model().get_value(iter, 0)
        _logger.debug("selected recent dir %s", d)
        self.context.do_cd(d)        
    
    def __mk_snapshot(self, value, odisp):
        return HotwireOutputState(value, odisp.get_pipeline.get_output_type(), odisp.get_pipeline.is_singlevalue)
    
    def __do_snapshot(self, ref, selected=False):
        odisp = ref()
        if not odisp:
            return None
        return odisp.make_snapshot(selected=selected)        
    
    def get_current_output_metadata(self):
        odisp = self.__outputs.get_current()
        if not odisp:
            return None
        return odisp.get_pipeline().get_output_metadata()
    
    def get_current_output_ref(self):
        odisp = self.__outputs.get_current()
        if odisp:
            return weakref.ref(odisp)
        return None
    
    def snapshot_output(self, ref):
        return self.__do_snapshot(ref)
    
    def snapshot_selected_output(self, ref):
        return self.__do_snapshot(ref, selected=True)        
    
    def do_copy_url_drag_to_dir(self, urls, path):
        def fstrip(url):
            if url.startswith('file://'):
                return url[7:]
            return url
        fpaths = map(fstrip, urls.split('\r\n'))
        _logger.debug("path is %s, got drop paths: %s", path, fpaths)
        fpaths.append(path)
        self.internal_execute('cp', *fpaths)
    
    def __on_drag_data_received(self, tv, context, x, y, selection, info, etime):
        sel_data = selection.data
        self.do_copy_url_drag_to_dir(sel_data, self.context.get_cwd())
        
    def get_entry(self):
        return self.__input
    
    def grab_focus(self):
        self.__input.grab_focus()
        
    def completions_hide(self):
        self.__completions.hide_all()

    def __update_status(self):
        self.emit("title", self.get_title())

    def get_title(self):
        return self.context.get_cwd()

    def append_text(self, text):
        curtext = self.__input.get_property('text')
        if curtext and curtext[-1] != ' ':
            text = ' ' + text
        self.__input.set_property('text', curtext + text)
        
    def internal_execute_str(self, cmdtext):
        self.internal_execute(*Pipeline.tokenize(cmdtext))     

    def internal_execute(self, *args):
        pipeline = Pipeline.create(self.context, None, *args)
        self.execute_pipeline(pipeline, add_history=False, reset_input=False)        

    def execute_pipeline(self, pipeline,
                            add_history=True,
                            reset_input=True,
                            origtext=None):
        _logger.debug("pipeline: %s", pipeline)

        if pipeline.is_nodisplay():
            pipeline.execute_sync()

        curlang = self.get_active_lang()
        if add_history:
            text = origtext.strip()            
            self.context.history.append_command(curlang.uuid, text, self.context.get_cwd())
            self.__tabhistory.insert(0, (curlang.uuid, text))
            if len(self.__tabhistory) >= self.MAX_TABHISTORY:
                self.__tabhistory.pop(-1)
        if reset_input:
            self.__input.set_text("")
            self.__completion_token = None
            self.__completions.invalidate()

        self.__update_status()

        if pipeline.is_nodisplay():
            return

        self.__unset_welcome()

        self.__outputs.add_pipeline(pipeline)
        pipeline.execute(opt_formats=self.__outputs.get_current().get_opt_formats())
        
    def __unset_welcome(self):
        if not self.__welcome:
            return
        self.__paned.remove(self.__welcome_align)
        self.__paned.pack_end(self.__topbox, expand=True)
        self.__topbox.show_all()
        self.__welcome = None
        self.__welcome_align = None        

    def __execute(self):
        self.__completions.hide_all()
        try:
            self.__do_parse(partial=False, resolve=True)
        except hotwire.command.PipelineParseException, e:
            self.push_error(_("Failed to parse pipeline"), secondary=e.args[0])
            return
                
        text = self.__input.get_property("text")
                
        _logger.debug("executing '%s'", self.__parsed_pipeline)
        if not self.__parsed_pipeline:
            _logger.debug("Nothing to execute")
            return

        # clear message if any
        self.push_msg('')
        
        self.execute_pipeline(self.__parsed_pipeline, origtext=text)
        
    @log_except(_logger)
    def __on_histitem_selected(self, popup, histitem):
        _logger.debug("got history item selected: %s", histitem)
        if histitem is None:
            _logger.debug("no history item, doing popdown")
            self.__completions.hide_all()
            return
        (lang_uuid, histtext) = histitem
        lang = PipelineLanguageRegistry.getInstance()[lang_uuid]
        self.__lang_button.set_lang(lang)
        self.__input.set_text(histtext)
        self.__input.set_position(-1)

    @log_except(_logger)
    def __on_completion_selected(self, popup, completion):
        _logger.debug("got completion selected")
        if not completion:
            _logger.debug("no completion, doing popdown")
            self.__completions.hide_all()
            return
        self.__insert_single_completion(completion)

    def __on_completions_loaded(self, compls):
        assert self.__completion_async_blocking
        _logger.debug("completions loaded")        
        self.__insert_completion()

    def __do_completion(self):
        _logger.debug("requesting completion")
        if self.__parse_stale:
            try:
                self.__do_parse(partial=True, resolve=False)
            except hotwire.command.PipelineParseException, e:
                self.push_error(_('Failed to parse pipeline'), secondary=e.args[0])
                return
            self.__do_complete()
        self.__insert_completion()
            
    def __insert_single_completion(self, completion):
        text = completion.suffix
        # FIXME move this into CompletionSystem
        tobj = completion.target
        if not (isinstance(tobj, File) and tobj.is_directory):
            text += " "
        self.__insert_completing_text(text)
            
    def __insert_completing_text(self, text):
        curtext = self.__input.get_property("text")        
        pos = self.__input.get_position()
        self.__completion_suppress = True
        self.__input.set_property('text', curtext + text)
        self.__input.set_position(pos + len(text))
        self.__completion_suppress = False
        self.__parse_stale = True
        self.__completions.invalidate()
        self.__completions.hide_all()
        self.__queue_parse()           
            
    def __insert_completion(self):
        results = self.__completions.completion_request()
        if results is True:
            self.__completion_async_blocking = True
            _logger.debug("results pending, setting blocking=TRUE")
            self.__completions.hide_all()
            return
        if results is None:
            _logger.debug("no active completer, request dropped")
            return

        if self.__completion_async_blocking:
            _logger.debug("setting blocking=FALSE")            
            self.__completion_async_blocking = False
        if len(results.results) == 0:
            _logger.debug("no completions")
            return
        if len(results.results) == 1:
            _logger.debug("single completion: %r", results.results[0])            
            self.__insert_single_completion(results.results[0])
        elif results.common_prefix:
            _logger.debug("completion common prefix: %r", results.common_prefix)
            self.__insert_completing_text(results.common_prefix)
        else:
            # We should have popped up the display list
            pass

    def __handle_completion_key(self, e):
        curtext = self.__input.get_property("text")
        state = self.__completions.get_state()
        if (state is not None) and e.keyval == gtk.gdk.keyval_from_name('Return'):
            self.__completions.activate_selected()
            return True         
        elif e.keyval == gtk.gdk.keyval_from_name('Tab'):
            if curtext:
                self.__do_completion()
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('r') and e.state & gtk.gdk.CONTROL_MASK:
            self.__do_parse(resolve=False)            
            if state is None:
                if curtext:
                    self.__completions.popup_global_history()
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Up'):
            if state is None:
                self.__completions.popup_tab_history()
            else:
                self.__completions.select_next()
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Down'):
            self.__completions.select_prev()
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Page_Up'):
            return self.__completions.page_up()
        elif e.keyval == gtk.gdk.keyval_from_name('Page_Down'):           
            return self.__completions.page_down()  
        elif e.keyval == gtk.gdk.keyval_from_name('Escape'):
            self.__clear_msg()
            self.__completion_async_blocking = False
            self.__completions.hide_all()
            return True
        return False

    def __on_entry_focus_lost(self, entry, e):
        self.__completions.hide_all()
        
    @log_except(_logger)
    def __on_toplevel_keypress(self, s2, e):
        if e.keyval == gtk.gdk.keyval_from_name('Escape'):
            self.grab_focus()
            return True 
        return False       

    @log_except(_logger)
    def __on_input_keypress(self, e):
        curtext = self.__input.get_property("text")
        
        self.__requeue_parse()
        
        if self.__completion_async_blocking:
            return True

        if self.__handle_completion_key(e):
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Return'):
            self.__execute()
            return True
        elif self.__emacs_bindings and self.__handle_emacs_binding(e):
            return True     
        else:
            return False
        
    def __handle_emacs_binding(self, e):
        if e.keyval == gtk.gdk.keyval_from_name('b') \
             and e.state & gtk.gdk.CONTROL_MASK:
            self.__input.emit('move-cursor', gtk.MOVEMENT_LOGICAL_POSITIONS, -1, 0)
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('f') \
             and e.state & gtk.gdk.CONTROL_MASK:
            self.__input.emit('move-cursor', gtk.MOVEMENT_LOGICAL_POSITIONS, 1, 0)
            return True        
        elif e.keyval == gtk.gdk.keyval_from_name('f') \
             and e.state & gtk.gdk.MOD1_MASK:
            self.__input.emit('move-cursor', gtk.MOVEMENT_WORDS, 1, False)
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('b') \
             and e.state & gtk.gdk.MOD1_MASK:
            self.__input.emit('move-cursor', gtk.MOVEMENT_WORDS, -1, False)
            return True 
        elif e.keyval == gtk.gdk.keyval_from_name('A') \
             and e.state & gtk.gdk.CONTROL_MASK:
            self.__input.emit('move-cursor', gtk.MOVEMENT_BUFFER_ENDS, -1, True)
            return True               
        elif e.keyval == gtk.gdk.keyval_from_name('a') \
             and e.state & gtk.gdk.CONTROL_MASK:
            self.__input.emit('move-cursor', gtk.MOVEMENT_BUFFER_ENDS, -1, False)
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('e') \
             and e.state & gtk.gdk.CONTROL_MASK:
            self.__input.emit('move-cursor', gtk.MOVEMENT_BUFFER_ENDS, 1, False)
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('E') \
             and e.state & gtk.gdk.CONTROL_MASK:
            self.__input.emit('move-cursor', gtk.MOVEMENT_BUFFER_ENDS, 1, True)
            return True        
        elif e.keyval == gtk.gdk.keyval_from_name('k') \
             and e.state & gtk.gdk.CONTROL_MASK:
            self.__input.emit('delete-from-cursor', gtk.DELETE_PARAGRAPH_ENDS, 1)
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('d') \
             and e.state & gtk.gdk.MOD1_MASK:
            self.__input.emit('delete-from-cursor', gtk.DELETE_WORD_ENDS, 1)
            return True                       
        return False
    
    def __unqueue_parse(self):
        if self.__idle_parse_id > 0:
            gobject.source_remove(self.__idle_parse_id)
        self.__idle_parse_id = 0

    def __requeue_parse(self):
        self.__unqueue_parse()
        self.__idle_parse_id = gobject.timeout_add(450, self.__idle_do_parse_and_complete)        

    def __queue_parse(self):
        self.__parse_stale = True
        if self.__idle_parse_id > 0:
            return
        _logger.debug("queuing parse")
        self.__requeue_parse()

    def __do_parse_requeue(self):
        self.__do_parse()
        self.__requeue_parse()

    @log_except(_logger)
    def __idle_do_parse_and_complete(self):
        self.__idle_parse_id = 0
        if not self.__parse_stale:
            return
        if not self.__do_parse(resolve=False):
            _logger.debug('failed to parse')
            return
        self.__do_complete()
        
    def __completion_supported(self):
        # We only support HotwirePipe at the moment
        return self.get_active_lang().uuid == '62270c40-a94a-44dd-aaa0-689f882acf34'        
        
    def __do_complete(self):
        ### TODO: move more of this stuff into hotwire_ui/completion.py
        self.__completion_token = None        
        pos = self.__input.get_position()
        prev_token = None
        completer = None
        verb = None
        verbcmd = None
        addprefix = None
        # can happen when input is empty
        if not self.__parsed_pipeline:
            _logger.debug("no tree, no completion")
            self.__completions.invalidate()            
            return
        if not self.__completion_supported():
            _logger.debug("unsupported completion lang")
            self.__completions.invalidate()          
            return        
        commands = list(self.__parsed_pipeline)
        for i,cmd in enumerate(commands):
            commands[i] = list(cmd.get_tokens())
        for i,cmd in enumerate(commands):
            verb = cmd[0]
            verbcmd = self.__parsed_pipeline[i]            
            if pos >= verb.start and pos <= verb.end :
                _logger.debug("pos %r generating verb completions for '%s' (%r %r)", verb.text, pos, verb.start, verb.end)
                completer = self.__verb_completer
                self.__completion_token = verb
                break
            prev_token = verb.text
            cmdargs = cmd[1:]
            cmdlen = len(cmdargs)
            _logger.debug("not in verb, examining %d tokens for %r", cmdlen, verbcmd)
            for i,token in enumerate(cmdargs):
                if not ((pos >= token.start) and (pos <= token.end)) and not (i == cmdlen-1):
                    _logger.debug("skipping token (%s %s) out of %d: %s ", token.start, token.end, pos, token.text)
                    prev_token = token
                    continue
                _logger.debug("generating token completions from %s for '%s'", completer, token.text)
                self.__completion_token = token
                break
            if not self.__completion_token:
                _logger.debug("no completion token found, position at end")
                self.__completion_token = hotwire.command.ParsedToken('', start=pos)              
            completer = verbcmd.builtin.get_completer(self.context, cmd, i)
            if not completer:
                # This happens because of the way we auto-inject 'sys'
                if verbcmd.builtin.name == 'sys' and cmdlen == 0:
                    completer = self.__verb_completer
                else:
                    completer = self.__token_completer
        self.__completer = completer
        _logger.debug("generating completions from token: %r completer: %r", self.__completion_token, self.__completer)
        if self.__completer:
            self.__completions.set_completion(completer, self.__completion_token.text, self.context)
        else:
            _logger.debug("no valid completions found")
            self.__completions.invalidate()

    def __do_parse(self, partial=True, resolve=True):
        if (not self.__parse_stale) and (self.__parse_resolved == resolve) and (self.__parse_partial == partial):
            return True
        text = self.__input.get_property("text")
        try:
            self.__parsed_pipeline = self.__pipeline_factory.parse(text, accept_partial=partial, 
                                                                         curlang=self.__langtype,
                                                                         resolve=resolve)
        except hotwire.command.PipelineParseException, e:
            _logger.debug("parse failed, current syntax=%s", self.__langtype, exc_info=True)
            self.__parsed_pipeline = None
            if (not partial):
                raise e
            return False
        _logger.debug("parse tree: %s", self.__parsed_pipeline)
        self.__parse_stale = False
        self.__parse_resolved = resolve
        self.__parse_partial = partial
        self.__unqueue_parse()
        return True

    def __on_input_changed(self):
        if self.__completion_suppress:
            _logger.debug("Suppressing completion change")
            return
        self.__completions.invalidate()
        if self.__completion_active:
            self.__completion_active = False
        curvalue = self.__input.get_property("text")
        if not self.__history_suppress:
            # Change '' to None, because '' has special value to mean
            # show all history, which we don't do by default
            self.__completions.set_history_search(self.get_active_lang().uuid, curvalue or None)
        self.__queue_parse()

    def __on_scroll_offset(self, i, offset):
        offset = i.get_property('scroll-offset')
        
    def __on_pref_changed(self, prefs, key, value):
        self.__sync_prefs(prefs)
        
    def __sync_prefs(self, prefs):
        _logger.debug("syncing prefs")
        emacs = prefs.get_pref('ui.emacs', default=False)
        if self.__emacs_bindings == emacs:
            return
        self.__emacs_bindings = emacs
        _logger.debug("using Emacs keys: %s", emacs)
            
class HotWindow(gtk.Window):
    ascii_nums = [long(x+ord('0')) for x in xrange(10)]

    def __init__(self, factory=None, is_initial=False, subtitle='', **kwargs):
        super(HotWindow, self).__init__()

        self.__prefs_dialog = None

        vbox = gtk.VBox()
        self.add(vbox)
        self.__ui_string = """
<ui>
  <menubar name='Menubar'>
    <menu action='FileMenu'>
      <menuitem action='NewWindow'/>
      <menuitem action='NewTab'/>
      <menuitem action='NewTermTab'/>
      <separator/>
      <menuitem action='DetachTab'/>
      <placeholder name='FileDetachAdditions'>
      </placeholder>
      <separator/>
      <menuitem action='Close'/>
    </menu>
    <menu action='EditMenu'>
      <placeholder name='EditMenuAdditions'/>
      <separator/>
      <menuitem action='Preferences'/>
    </menu>
    <menu action='ViewMenu'>
      <menuitem action='Fullscreen'/>
      <separator/>
    </menu>
    <placeholder name='WidgetMenuAdditions'>
    </placeholder>
    <menu action='ToolsMenu'>
      <menuitem action='HelpCommand'/>      
      <menuitem action='About'/>
    </menu>
  </menubar>
</ui>
"""       
        self.__create_ui()
        vbox.pack_start(self.__ui.get_widget('/Menubar'), expand=False)

        self.__pyshell = None
        self.factory = factory
        
        self.__fullscreen_mode = False

        self.__notebook = gtk.Notebook()
        self.__notebook.connect('switch-page', lambda n, p, pn: self.__focus_page(pn))
        self.__notebook.show()
        self.__tabs_visible = self.__notebook.get_show_tabs()

        self.__geom_hints = {}
        self.__old_char_width = 0
        self.__old_char_height = 0
        self.__old_geom_widget = None
        
        self.__closesigs = {}
        
        self.__curtab_is_hotwire = False

        # Records the last tab index from which we created a new tab, so we 
        # can switch back when closed, unless the user manually switched tabs
        # between.
        self.__pre_autoswitch_index = -1
        
        self.set_default_size(720, 540)
        self.set_title('Hotwire' + subtitle)
        if os.getenv("HOTWIRE_UNINSTALLED"):
            # For some reason set_icon() doesn't work even though we extend the theme path
            # do it manually.
            iinf = gtk.icon_theme_get_default().lookup_icon('hotwire', 24, 0)
            if iinf:
                self.set_icon_from_file(iinf.get_filename())
        else:
            self.set_icon_name("hotwire")
        
        prefs = Preferences.getInstance()
        prefs.monitor_prefs('ui.', self.__on_pref_changed)
        self.__sync_prefs(prefs)

        self.connect("delete-event", lambda w, e: False)

        self.connect("key-press-event", self.__on_keypress)
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.__on_buttonpress)

        vbox.add(self.__notebook)
        vbox.show()

        if 'initwidget' in kwargs:
            self.new_tab_widget(*kwargs['initwidget'])
        else:
            self.new_tab_hotwire(**kwargs)
            
    def __on_pref_changed(self, prefs, key, value):
        self.__sync_prefs(prefs)
        
    def __sync_prefs(self, prefs):
        _logger.debug("syncing prefs")
        accels = prefs.get_pref('ui.menuaccels', default=True)
        if self.__using_accels == accels:
            return
        self.__sync_action_acceleration()
        
    def __sync_action_acceleration(self):
        accels = Preferences.getInstance().get_pref('ui.menuaccels', default=True)
        self.__using_accels = accels                
        def frob_action(action):
            name = action.get_name()
            if not name.endswith('Menu'):
                return
            uiname = action.get_property('label')
            # FIXME this is gross.
            menuitem = self.__ui.get_widget('/Menubar/' + name)
            if not menuitem:
                menuitem = self.__ui.get_widget('/Menubar/WidgetMenuAdditions/' + name)
            label = menuitem.get_child()
            if accels:
                label.set_text_with_mnemonic(uiname)
            else:
                noaccel = uiname.replace('_', '')
                label.set_text(noaccel)
        for action in self.__ag.list_actions():
            frob_action(action)
        for uistr,actiongroup in self.__tab_ui_merge_ids:
            for action in actiongroup.list_actions():
                frob_action(action)                

    def get_ui(self):
        return self.__ui

    def __create_ui(self):
        self.__using_accels = True
        self.__ag = ag = gtk.ActionGroup('WindowActions')
        self.__actions = actions = [
            ('FileMenu', None, _('_File')),
            ('NewTermTab', gtk.STOCK_NEW, _('New T_erminal Tab'), '<control><shift>T',
             _('Open a new terminal tab'), self.__new_term_tab_cb),
            ('DetachTab', gtk.STOCK_JUMP_TO, _('_Detach Tab'), '<control><shift>D',
             _('Deatch current tab'), self.__detach_tab_cb),
            ('Close', gtk.STOCK_CLOSE, _('_Close'), '<control><shift>W',
             _('Close the current tab'), self.__close_cb),
            ('EditMenu', None, _('_Edit')),        
            ('ViewMenu', None, _('_View')),
            ('Preferences', gtk.STOCK_PREFERENCES, _('Preferences'), None, _('Change preferences'), self.__preferences_cb),                                       
            ('ToolsMenu', None, _('_Tools')),
            ('HelpCommand', 'gtk-help', _('_Help'), None, _('Display help command'), self.__help_cb),                       
            ('About', gtk.STOCK_ABOUT, _('_About'), None, _('About Hotwire'), self.__help_about_cb),
            ]
        self.__nonterm_actions = [
            ('NewWindow', gtk.STOCK_NEW, _('_New Window'), '<control>n',
             _('Open a new window'), self.__new_window_cb),
            ('NewTab', gtk.STOCK_NEW, _('New _Tab'), '<control>t',
             _('Open a new tab'), self.__new_tab_cb)]
        self.__toggle_actions = [
            ('Fullscreen', gtk.STOCK_FULLSCREEN, _('Fullscreen'), 'F11', _('Switch to full screen mode'), self.__fullscreen_cb)
            ]
        ag.add_actions(actions)
        ag.add_actions(self.__nonterm_actions)
        ag.add_toggle_actions(self.__toggle_actions)
        self.__ui = gtk.UIManager()
        self.__ui.insert_action_group(ag, 0)
        self.__ui.add_ui_from_string(self.__ui_string)
        self.__tab_ui_merge_ids = []
        self.__ui_merge_page_id = None
        self.__nonterm_accels_installed = True
        self.add_accel_group(self.__ui.get_accel_group())       

    def __show_pyshell(self):
        if self.__pyshell:
            self.__pyshell.destroy()
        self.__pyshell = hotwire_ui.pyshell.CommandShell({'curshell': lambda: locate_current_shell(self)},
                                                         savepath=os.path.join(Filesystem.getInstance().get_conf_dir(), 'pypad.py'),
                                                         parent=self)
        self.__pyshell.set_icon_name('hotwire')        
        self.__pyshell.set_title(_('Hotwire PyShell'))
        self.__pyshell.show_all()      

    def __on_buttonpress(self, s2, e):
        widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())
        if hasattr(widget, 'on_mouse_press'):
            if widget.on_mouse_press(e):
                return True
        return False
    
    def __get_curtab_cwd(self):
        widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())
        is_hw = widget.get_data('hotwire-is-hotwire')
        if is_hw:
            cwd = widget.context.get_cwd()
        else:
            cwd = os.path.expanduser('~')
        return cwd        
    
    def __new_window_cb(self, action):
        self.new_win_hotwire(initcwd=self.__get_curtab_cwd(), initcmd='ls')

    def __new_tab_cb(self, action):
        self.new_tab_hotwire(initcwd=self.__get_curtab_cwd(), initcmd='ls')

    def __new_term_tab_cb(self, action):
        self.new_tab_term(None, autoclose=True)
        
    def __detach_tab_cb(self, action):
        widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())
        title = self.__get_title(widget)
        self.__on_widget_closed(widget)
        self.new_win_widget(widget, title)

    def __close_cb(self, action):
        self.__remove_page_widget(self.__notebook.get_nth_page(self.__notebook.get_current_page()))
        
    def __fullscreen_cb(self, action):
        mode = self.__fullscreen_mode
        self.__fullscreen_mode = not self.__fullscreen_mode
        if mode:
            self.unfullscreen()
        else:
            self.fullscreen()         

    def __preferences_cb(self, action):
        if not self.__prefs_dialog:
            self.__prefs_dialog = PrefsWindow()
        self.__prefs_dialog.show_all()
        
    def __help_cb(self, action):
        widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())
        is_hw = widget.get_data('hotwire-is-hotwire')
        if is_hw:
            widget.internal_execute('help')
        else:
            self.new_tab_hotwire(initcmd='help')

    def __help_about_cb(self, action):
        dialog = HotwireAboutDialog()
        dialog.run()
        dialog.destroy()

    @log_except(_logger)
    def __on_keypress(self, s2, e):
        if e.keyval == gtk.gdk.keyval_from_name('s') and \
             e.state & gtk.gdk.CONTROL_MASK and \
             e.state & gtk.gdk.MOD1_MASK:
            self.__show_pyshell()
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Page_Up') and \
             e.state & gtk.gdk.CONTROL_MASK:
            idx = self.__notebook.get_current_page() 
            self.__notebook.set_current_page(idx-1)
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Page_Down') and \
             e.state & gtk.gdk.CONTROL_MASK:
            idx = self.__notebook.get_current_page() 
            self.__notebook.set_current_page(idx+1)
            return True
        elif e.keyval in HotWindow.ascii_nums and \
             e.state & gtk.gdk.MOD1_MASK:
            self.__notebook.set_current_page(e.keyval-ord('0')-1) #extra -1 because tabs are 0-indexed
            return True
        return False

    @log_except(_logger)
    def __focus_page(self, pn):
        _logger.debug("got focus page, idx: %d", pn)
        # User switched tabs, reset tab affinity
        self.__preautoswitch_index = -1
        
        # Basically the entire pile of hacks below here is adapted from gnome-terminal.
        # We're actually more complex in that we have non-terminals and terminals tabs
        # in the same notebook.
        # One key hack is that we hide the widget for the non-active tab.  This seems
        # to avoid having it influence the size of the notebook when we don't want it to.
        # Note when we switch to Hotwire tabs, we set the geometry hints to nothing;
        # only terminal tabs get hints set.
        widget = self.__notebook.get_nth_page(pn)
        is_hw = widget.get_data('hotwire-is-hotwire')
        old_idx = self.__notebook.get_current_page()
        if old_idx != pn and old_idx >= 0:
            old_widget = self.__notebook.get_nth_page(old_idx)
            old_is_hw = old_widget.get_data('hotwire-is-hotwire')
            if hasattr(old_widget, 'hide_internals'):
                _logger.debug("hiding widget at idx %s", old_idx)
                old_widget.hide_internals()
        else:
            old_widget = None
            old_is_hw = False
        if hasattr(widget, 'show_internals'):
            _logger.debug("showing widget at idx %s", old_idx)
            widget.show_internals()            
        if is_hw:
            gobject.idle_add(self.set_focus, widget.get_entry())
            self.set_geometry_hints(widget, **{})            
            self.__old_geom_widget = widget   
        elif hasattr(widget, 'get_term_geometry'):
            (cw, ch, (xp, yp)) = widget.get_term_geometry()
            if not (cw == self.__old_char_width and ch == self.__old_char_height and widget == self.__old_geom_widget):
                _logger.debug("resetting geometry on %s %s %s => %s %s", widget, self.__old_char_width, self.__old_char_height, cw, ch)
                kwargs = {'base_width':xp,
                          'base_height':yp,
                          'width_inc':cw,
                          'height_inc':ch,
                          'min_width':xp+cw*4,
                          'min_height':yp+ch*2}
                _logger.debug("setting geom hints: %s", kwargs)
                self.__geom_hints = kwargs
                self.set_geometry_hints(widget, **kwargs)
                self.__old_char_width = cw
                self.__old_char_height = ch
                self.__old_geom_widget = widget
        
        if old_is_hw:
            old_widget.completions_hide()
        
        self.__curtab_is_hotwire = is_hw
                
        if pn != self.__ui_merge_page_id:
            for id,actions in self.__tab_ui_merge_ids:
                self.__ui.remove_ui(id)
                self.__ui.remove_action_group(actions)
                ## Need to call ensure_update here because otherwise accelerators
                ## from the new UI will not be installed (I believe this is due
                ## to the way X keyboard grabs work)
                self.__ui.ensure_update()
            self.__ui_merge_page_id = pn
            self.__tab_ui_merge_ids = []                
            if hasattr(widget, 'get_ui_pairs'):
                for uistr,actiongroup,init in widget.get_ui_pairs():
                    mergeid = self.__ui.add_ui_from_string(uistr)
                    self.__ui.insert_action_group(actiongroup, -1)
                    if init != None:
                        init(self.__ui)
                    self.__tab_ui_merge_ids.append((mergeid, actiongroup))
                self.__sync_action_acceleration()

        install_accels = is_hw
        _logger.debug("current accel install: %s new: %s", self.__nonterm_accels_installed, install_accels)
        if self.__nonterm_accels_installed != install_accels:
            if install_accels:
                _logger.debug("connecting nonterm accelerators")
            else:
                _logger.debug("disconnecting nonterm accelerators")    
            for action in self.__nonterm_actions:
                actionitem = self.__ag.get_action(action[0])
                if install_accels:
                    actionitem.connect_accelerator()
                else:
                    actionitem.disconnect_accelerator()
            self.__nonterm_accels_installed = install_accels
            
        self.__sync_title(pn)
            
    def __get_title(self, widget):
        tl = widget.get_data('hotwire-tab-label')
        if not tl:
            return None
        title = _('%s - Hotwire') % (tl.get_text(),)
        # Totally gross hack; this avoids the current situation of
        # 'sudo blah' showing up with a title of 'term -w sudo blah'.
        # Delete this if we revisit the term -w situation.
        if title.startswith('term -w'):
            title = title[7:]
        return title    
            
    def __sync_title(self, pn=None):
        if pn is not None:
            pagenum = pn
        else:
            pagenum = self.__notebook.get_current_page()
        widget = self.__notebook.get_nth_page(pagenum)
        title = self.__get_title(widget)
        if not title:
            return
        self.set_title(title)
            
    def new_tab_hotwire(self, is_initial=False, **kwargs):
        hw = Hotwire(window=self, ui=self.__ui, **kwargs)
        hw.set_data('hotwire-is-hotwire', True)

        idx = self.__notebook.append_page(hw)
        if hasattr(self.__notebook, 'set_tab_reorderable'):
            self.__notebook.set_tab_reorderable(hw, True)
        label = self.__add_widget_title(hw)

        def on_title(h, title):
            label.set_text(title)
            self.__sync_title()
        hw.connect('title', on_title)
        on_title(hw, hw.get_title())

        hw.connect('new-tab-widget', lambda h, *args: self.new_tab_widget(*args))
        hw.connect('new-window-cmd', lambda h, cmd: self.new_win_hotwire(initcmd_widget=cmd))        
        hw.show_all()
        self.__notebook.set_current_page(idx)
        self.set_focus(hw.get_entry())
        
    def new_tab_term(self, cmd, cwd=None, autoclose=False):
        target_cwd = cwd or self.__get_curtab_cwd()
        term = Terminal.getInstance().get_terminal_widget_cmd(target_cwd, cmd, '', autoclose=autoclose)
        self.new_tab_widget(term, 'term')        

    def __sync_tabs_visible(self):
        oldvis = self.__tabs_visible
        self.__tabs_visible = len(self.__notebook.get_children()) > 1
        if self.__tabs_visible != oldvis:
            self.__notebook.set_show_tabs(self.__tabs_visible)
        self.__ag.get_action('DetachTab').set_sensitive(self.__tabs_visible)    

    def __remove_page_widget(self, w):
        savedidx = self.__preautoswitch_index
        idx = self.__notebook.page_num(w)
        _logger.debug("tab closed, preautoswitch idx: %d current: %d", savedidx, idx)
        self.__notebook.remove_page(idx)
        self.__sync_tabs_visible()
        if w in self.__closesigs:
            w.disconnect(self.__closesigs[w])
            del self.__closesigs[w]
        if self.__notebook.get_n_pages() == 0:
            self.destroy()                
        elif savedidx >= 0:
            if idx < savedidx:
                savedidx -= 1
            self.__notebook.set_current_page(savedidx)
            
    def __on_widget_closed(self, w):
        if w in self.__closesigs:
            w.disconnect(self.__closesigs[w])
            del self.__closesigs[w]
        self.__remove_page_widget(w)

    def __add_widget_title(self, w):
        hbox = gtk.HBox()
        label = gtk.Label('<notitle>')
        label.set_selectable(False)
        label.set_ellipsize(pango.ELLIPSIZE_END)
        hbox.pack_start(hotwidgets.Align(label, padding_right=4), expand=True)

        close = gtk.Button()
        close.set_focus_on_click(False)
        close.set_relief(gtk.RELIEF_NONE)
        close.set_name('hotwire-tab-close')
        img = gtk.Image()
        img.set_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU)
        close.add(img)
        close.connect('clicked', lambda b: self.__close_tab(w))        
        (width, height) = gtk.icon_size_lookup_for_settings(label.get_settings(), gtk.ICON_SIZE_MENU)
        close.set_size_request(width + 2, height + 2)
        hbox.pack_start(close, expand=False)
        hbox.show_all()
        self.__notebook.set_tab_label(w, hbox)
        w.set_data('hotwire-tab-label', label)
        self.__notebook.set_tab_label_packing(w, True, True, gtk.PACK_START)
        self.__sync_tabs_visible()
        return label

    def __close_tab(self, w):
        self.__remove_page_widget(w)
        w.destroy()

    def new_tab_widget(self, widget, title):
        widget.set_data('hotwire-is-hotwire', False)
        savedidx = self.__notebook.get_current_page()
        idx = self.__notebook.append_page(widget)
        if hasattr(self.__notebook, 'set_tab_reorderable'):
            self.__notebook.set_tab_reorderable(widget, True)
        label = self.__add_widget_title(widget)
        label.set_text(title)
        widget.show_all()
        self.__notebook.set_current_page(idx)
        self.__closesigs[widget] = widget.connect('closed', self.__on_widget_closed)
        _logger.debug("preautoswitch idx: %d", savedidx)
        self.__preautoswitch_index = savedidx

    def new_win_hotwire(self, **kwargs):
        widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())
        is_hw = widget.get_data('hotwire-is-hotwire')
        if is_hw and 'initcwd' not in kwargs:
            kwargs['initcwd'] = widget.context.get_cwd()
        win = HotWindowFactory.getInstance().create_window(**kwargs)
        win.show()
        
    def new_win_widget(self, widget, title):
        win = HotWindowFactory.getInstance().create_window(initwidget=(widget, title))
        win.show()
        
    def get_current_widget(self):
        widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())
        is_hw = widget.get_data('hotwire-is-hotwire')
        if is_hw:
            return widget
        return None        

class HotWindowFactory(Singleton):
    def __init__(self):
        super(HotWindowFactory, self).__init__()
        self.__windows = set()
        self.__active_window = None
        self.__sticky_keywords = {'subtitle': ''}

    def create_initial_window(self, *args, **kwargs):
        return self.create_window(is_initial=True, *args, **kwargs)

    def create_window(self, is_initial=False, *args, **kwargs):
        _logger.debug("creating window")
        if is_initial:
            for k,v in kwargs.iteritems():
                if self.__sticky_keywords.has_key(k):
                    self.__sticky_keywords[k] = v
            if 'initcmd' not in kwargs:
                kwargs['initcmd'] = 'help'
        for k,v in self.__sticky_keywords.iteritems():
            if not kwargs.has_key(k):
                kwargs[k] = v
        win = HotWindow(factory=self, is_initial=is_initial, **kwargs)
        win.connect('destroy', self.__on_win_destroy)
        win.connect('notify::is-active', self.__on_window_active)        
        self.__windows.add(win)
        if not self.__active_window:
            self.__active_window = win
        return win
    
    @log_except(_logger)
    def run_tty(self, timestamp, cwd, args):
        """Called from remoting to execute command in a terminal."""
        active = self.__active_window
        if not active:
            return
        active.new_tab_term(args, cwd=cwd)
        if timestamp > 0:
            active.present_with_time(timestamp)
        else:
            active.present()          

    def __on_win_destroy(self, win):
        _logger.debug("got window destroy")
        self.__windows.remove(win)
        if win == self.__active_window and len(self.__windows) > 0:
            # Pick one.
            self.__active_window = self.__windows.__iter__().next()
        if len(self.__windows) == 0:
            gtk.main_quit()

    def __on_window_active(self, win, *args):
        active = win.get_property('is-active')
        if active:
            self.__active_window = win
