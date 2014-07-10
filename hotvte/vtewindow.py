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
import signal

import gtk,gobject,pango
import dbus,dbus.glib,dbus.service

from hotvte.vteterm import VteTerminalWidget

from hotwire_ui.quickfind import QuickFindWindow
from hotwire_ui.aboutdialog import HotwireAboutDialog

_logger = logging.getLogger("hotvte.VteWindow")

class QuickSwitchTabWindow(QuickFindWindow):
    def __init__(self, vtewin):
        self.__vtewin = vtewin        
        super(QuickSwitchTabWindow, self).__init__(_('Tab Search'),
                                                   parent=vtewin)
        
    def _do_search(self, text):
        for widget in self.__vtewin.get_tabs():
            title = widget.get_title()
            markup = self._markup_search(title, text)
            if markup is not None:
                yield (title, markup, None)

class TabbedVteWidget(VteTerminalWidget):
    def __init__(self, cmd=None, *args, **kwargs):
        super(TabbedVteWidget, self).__init__(cmd=cmd, *args, **kwargs)
        self.__title = ' '.join(cmd)
        
    def get_title(self):
        return self.__title

class VteWindow(gtk.Window):
    ascii_nums = [long(x+ord('0')) for x in xrange(10)]    
    def __init__(self, factory=None, title=None, icon_name=None, **kwargs):
        super(VteWindow, self).__init__()
        
        self.__factory = factory
        
        self.__old_char_height = 0
        self.__old_char_width = 0
        self.__old_geom_widget = None
        
        vbox = gtk.VBox()
        self.add(vbox)
        self.__ui_string = """
<ui>
  <menubar name='Menubar'>
    <menu action='FileMenu'>
      <placeholder name='FileAdditions'/>
      <separator/>
      <menuitem action='TabSearch'/>      
      <menuitem action='DetachTab'/>
      <separator/>
      <menuitem action='Close'/>
    </menu>
    <menu action='EditMenu'>
      <menuitem action='Copy'/>
      <menuitem action='Paste'/>
      <separator/>
      <placeholder name='EditAdditions'/>      
    </menu>
    <menu action='ViewMenu'>
      <separator/>
      <placeholder name='ViewAdditions'/>        
    </menu>
    <placeholder name='TermAppAdditions'/>
    <menu action='ToolsMenu'>
      <menuitem action='About'/>
    </menu>
  </menubar>
</ui>
"""       
        self.__create_ui()
        vbox.pack_start(self.__ui.get_widget('/Menubar'), expand=False)
        
        self.connect("key-press-event", self.__on_keypress)
                
        self.__title = title
        self.set_title(title)
        self.set_default_size(720, 540)
        if os.getenv('HOTWIRE_UNINSTALLED'):
            # For some reason set_icon() started failing...do it manually.
            iinf = gtk.icon_theme_get_default().lookup_icon(icon_name, 24, 0)
            self.set_icon_from_file(iinf.get_filename())
        else:
            self.set_icon_name(icon_name)
        self.connect("delete-event", lambda w, e: False)
        self.__tips = gtk.Tooltips()
        self.__notebook = gtk.Notebook()
        vbox.pack_start(self.__notebook)
        self.__notebook.connect('switch-page', self.__on_page_switch)
        self.__notebook.set_scrollable(True)
        self.__notebook.show()
        
        self.__tabs_visible = self.__notebook.get_show_tabs()
        
    def new_tab(self, args, cwd):
        widget = TabbedVteWidget(cmd=args, cwd=cwd)
        self.append_widget(widget)
        
    def remote_new_tab(self, args, cwd):
        self.new_tab(args, cwd)
        
    def append_widget(self, term):
        idx = self.__notebook.append_page(term)
        term.get_vte().connect('selection-changed', self.__sync_selection_sensitive)
        term.get_term().set_copy_paste_actions(self.__ag.get_action('Copy'), self.__ag.get_action('Paste'))
        if hasattr(term, 'has_close'):
            has_close = term.has_close()
        else:
            has_close = False
        if has_close:
            term.connect('close', self.__on_widget_close)
        if hasattr(self.__notebook, 'set_tab_reorderable'):
            self.__notebook.set_tab_reorderable(term, True)
        label = self.__add_widget_title(term)
        title = term.get_title()
        label.set_text(title)
        self.__tips.set_tip(label, title)
        term.show_all()
        self.__notebook.set_current_page(idx)
        term.get_vte().grab_focus()
        
    def _get_notebook(self):
        return self.__notebook

    def __on_page_switch(self, n, p, pn):
        _logger.debug("got page switch, pn=%d", pn)
        widget = self.__notebook.get_nth_page(pn)
        term = widget.get_vte()
        (cw, ch, (xp, yp)) = (term.get_char_width(), term.get_char_height(), term.get_padding())
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
            
        self.__sync_selection_sensitive()
        self.set_title('%s - %s' % (widget.get_title(),self.__title))
        
    def __on_keypress(self, s2, e):
        if e.keyval == gtk.gdk.keyval_from_name('Page_Up') and \
             e.state & gtk.gdk.CONTROL_MASK:
            idx = self.__notebook.get_current_page() 
            self.__notebook.set_current_page(idx-1)
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Page_Down') and \
             e.state & gtk.gdk.CONTROL_MASK:
            idx = self.__notebook.get_current_page() 
            self.__notebook.set_current_page(idx+1)
            return True
        elif e.keyval in VteWindow.ascii_nums and \
             e.state & gtk.gdk.MOD1_MASK:
            self.__notebook.set_current_page(e.keyval-ord('0')-1) #extra -1 because tabs are 0-indexed
            return True
        elif e.keyval == gtk.gdk.keyval_from_name('Return'):
            widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())        
            if widget.get_exited():
                self.__close_tab(widget)
                return True
        return False        
        
    def __create_ui(self):
        self.__using_accels = True
        self.__ag = ag = gtk.ActionGroup('WindowActions')
        self.__actions = actions = [
            ('FileMenu', None, _('File')),
            ('DetachTab', None, _('_Detach Tab'), '<control><shift>D', 'Move tab into new window', self.__detach_cb),
            ('TabSearch', None, '_Search Tabs', '<control><shift>L', 'Search across tab names', self.__quickswitch_tab_cb),
            ('Close', gtk.STOCK_CLOSE, _('_Close'), '<control><shift>W',
             'Close the current tab', self.__close_cb),
            ('EditMenu', None, _('Edit')),
            ('Copy', 'gtk-copy', _('_Copy'), '<control><shift>C', 'Copy selected text', self.__copy_cb),
            ('Paste', 'gtk-paste', _('_Paste'), '<control><shift>V', 'Paste text', self.__paste_cb),                   
            ('ViewMenu', None, _('View')),
            ('ToolsMenu', None, _('Tools')),                    
            ('About', gtk.STOCK_ABOUT, _('_About'), None, 'About HotVTE', self.__help_about_cb),
            ]
        ag.add_actions(actions)
        self.__ui = gtk.UIManager()
        self.__ui.insert_action_group(ag, 0)
        self.__ui.add_ui_from_string(self.__ui_string)
        self.add_accel_group(self.__ui.get_accel_group())
        
    def _merge_ui(self, actions, uistr):
        self.__ag.add_actions(actions)
        self.__ui_merge_id = self.__ui.add_ui_from_string(uistr)
        return self.__ag      
    
    def _get_ui(self):
        return self.__ui   

    def __add_widget_title(self, w):
        hbox = gtk.HBox()
        label = gtk.Label('<notitle>')
        label.set_selectable(False)
        label.set_ellipsize(pango.ELLIPSIZE_END)
        hbox.pack_start(label, expand=True)

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
        
    def __close_cb(self, action):
        self.__remove_page_widget(self.__notebook.get_nth_page(self.__notebook.get_current_page()))
        
    def __on_widget_close(self, widget):
        self.__remove_page_widget(widget)

    def __help_about_cb(self, action):
        dialog = HotwireAboutDialog()
        dialog.run()
        dialog.destroy()
        
    def get_tabs(self):
        return self.__notebook.get_children()
        
    def __quickswitch_tab_cb(self, action):
        w = QuickSwitchTabWindow(self)
        tabtitle = w.run_get_value()
        if tabtitle is None:
            return
        _logger.debug("got switch title: %r", tabtitle)
        for child in self.__notebook.get_children():
            if child.get_title() == tabtitle:
                self.__notebook.set_current_page(self.__notebook.page_num(child))
                break
        
    def __sync_tabs_visible(self):
        multitab = self.__notebook.get_n_pages() > 1
        self.__ag.get_action('DetachTab').set_sensitive(multitab)
        self.__ag.get_action('TabSearch').set_sensitive(multitab)        
        self.__notebook.set_show_tabs(multitab)        
        
    def __remove_page_widget(self, w):
        idx = self.__notebook.page_num(w)
        _logger.debug("tab closed, current: %d", idx)
        self.__notebook.remove_page(idx)
        self.__sync_tabs_visible()
        if self.__notebook.get_n_pages() == 0:
            self.destroy()      

    def __sync_selection_sensitive(self, *args):
        have_selection = self.__notebook.get_nth_page(self.__notebook.get_current_page()).get_vte().get_has_selection()
        self.__ag.get_action('Copy').set_sensitive(have_selection)

    def __copy_cb(self, a):
        _logger.debug("doing copy")
        widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())        
        widget.get_vte().copy_clipboard()        

    def __paste_cb(self, a):
        _logger.debug("doing paste")
        widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())
        widget.get_vte().paste_clipboard()

    def __detach_cb(self, a):
        widget = self.__notebook.get_nth_page(self.__notebook.get_current_page())
        self.__remove_page_widget(widget)               
        win = self.__factory.create_window()
        win.append_widget(widget)
        win.show_all()
                
_factory = None
class VteWindowFactory(gobject.GObject):
    __gsignals__ = {
        "shutdown" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }    
    def __init__(self, klass, window_args):
        super(VteWindowFactory, self).__init__()
        self.__windows = set()
        self.__klass = klass
        self.__window_args = window_args
        self.__sticky_keywords = {'subtitle': ''}
        self.__sticky_keywords.update(window_args)
        self.__recentwindow = None
        
    @staticmethod
    def getInstance():
        global _factory
        if _factory is None:
            _factory = VteWindowFactory()
        return _factory

    def create_initial_window(self, *args, **kwargs):
        win = self.create_window(is_initial=True, *args, **kwargs)
        self.__recentwindow = win
        return win

    def create_window(self, is_initial=False, *args, **kwargs):
        _logger.debug("creating window")
        if is_initial:
            for k,v in kwargs.iteritems():
                if self.__sticky_keywords.has_key(k):
                    self.__sticky_keywords[k] = v
        for k,v in self.__sticky_keywords.iteritems():
            if not kwargs.has_key(k):
                kwargs[k] = v
        win = self.__klass(factory=self, is_initial=is_initial, **kwargs)
        win.connect('notify::is-active', self.__on_window_active)
        win.connect('destroy', self.__on_win_destroy)
        self.__windows.add(win)
        return win
    
    def remote_new_tab(self, cmd, cwd):
        self.__recentwindow.remote_new_tab(cmd, cwd)
        return self.__recentwindow
    
    def __on_window_active(self, win, *args):
        active = win.get_property('is-active')
        if active:
            self.__recentwindow = win

    def __on_win_destroy(self, win):
        _logger.debug("got window destroy")
        self.__windows.remove(win)
        win.get_child().destroy()
        if len(self.__windows) == 0:
            self.emit('shutdown')
            gtk.main_quit()

class UiProxy(dbus.service.Object):
    def __init__(self, factory, bus_name, ui_iface, ui_opath):
        super(UiProxy, self).__init__(dbus.service.BusName(bus_name, bus=dbus.SessionBus()), ui_opath)
        self.__winfactory = factory
        # This is a disturbing hack.  But it works.
        def RunCommand(self, timestamp, istab, cmd, cwd):
            _logger.debug("Handling RunCommand method invocation ts=%r cmd=%r cwd=%r)", timestamp, cmd, cwd)
            if istab:
                curwin = self.__winfactory.remote_new_tab(cmd, cwd)
            else:
                raise NotImplementedError('can only create new tabs')
            timestamp = long(timestamp)+1
            if timestamp > 0:
                _logger.debug("presenting with timestamp %r", timestamp)
                curwin.present_with_time(timestamp)
            else:
                curwin.present()
        setattr(UiProxy, 'RunCommand', dbus.service.method(ui_iface, in_signature='ubass')(RunCommand))                

class VteRemoteControl(object):
    def __init__(self, name, bus_name=None, ui_opath=None, ui_iface=None):
        super(VteRemoteControl, self).__init__()
        self.__bus_name = bus_name or ('org.hotwireshell.HotVTE.' + name)
        self.__ui_opath = ui_opath or ('/hotvte/' + name + '/ui')
        self.__ui_iface = ui_iface or (self.__bus_name + '.Ui')
        
    def __parse_startup_id(self):
        startup_time = None
        try:
            startup_id_env = os.environ['DESKTOP_STARTUP_ID']
        except KeyError, e:
            startup_id_env = None
        if startup_id_env:
            idx = startup_id_env.find('_TIME')
            if idx > 0:
                idx += 5
                startup_time = int(startup_id_env[idx:])
        return startup_time        
        
    def single_instance(self, replace=False):
        proxy = dbus.SessionBus().get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        flags = 1 | 4 # allow replacement | do not queue
        if replace:
            flags = flags | 2 # replace existing
        _logger.debug("Requesting D-BUS name %s on session bus", self.__bus_name)            
        if not proxy.RequestName(self.__bus_name, dbus.UInt32(flags)) in (1,4):
            inst = dbus.SessionBus().get_object(self.__bus_name, self.__ui_opath)
            inst_iface = dbus.Interface(inst, self.__ui_iface)
            _logger.debug("Sending RunCommand to existing instance")
            # TODO support choosing tab/window
            starttime = self.__parse_startup_id()
            inst_iface.RunCommand(dbus.UInt32(starttime or 0), True, dbus.Array(sys.argv[1:], signature="s"), os.getcwd())
            sys.exit(0)
            os._exit(0)
        
    def get_proxy(self, factory):
        return UiProxy(factory, self.__bus_name, self.__ui_iface, self.__ui_opath)
    
class VteApp(object): 
    def __init__(self, name, windowklass):
        super(VteApp, self).__init__()
        self.__name = name
        self.__windowklass = windowklass
        
    def get_name(self):
        return self.__name
        
    def get_remote(self):
        return VteRemoteControl(self.get_name())
        
    def get_factory(self):
        return VteWindowFactory(self.__windowklass, {})
    
    def on_shutdown(self, factory):
        pass
    
class VteMain(object):
    def main(self, appklass):

        default_log_level = logging.WARNING
        if 'HOTVTE_DEBUG' in os.environ:
            default_log_level = logging.DEBUG
 
        import hotwire.logutil
        mods = os.environ.get('HOTVTE_DEBUG_MODULES', '')
        if mods:
            mods = mods.split(',')
        else:
            mods = []
        hotwire.logutil.init(default_log_level, mods, '')

        _logger.debug("logging initialized")

        locale.setlocale(locale.LC_ALL, '')
        import gettext
        gettext.install('hotwire')        
    
        gobject.threads_init()
        
        app = appklass()
        remote = app.get_remote()
        remote.single_instance()

        def on_about_dialog_url(dialog, link):
            import webbrowser
            webbrowser.open(link)    
        gtk.about_dialog_set_url_hook(on_about_dialog_url)
        gtk.rc_parse_string('''
style "hotwire-tab-close" {
  xthickness = 0
  ythickness = 0
}
widget "*hotwire-tab-close" style "hotwire-tab-close"
''')    
        if os.getenv('HOTWIRE_UNINSTALLED'):
            theme = gtk.icon_theme_get_default()
            imgpath = os.path.join(os.getenv('HOTWIRE_UNINSTALLED'), 'images')
            _logger.debug("appending to icon theme: %s", imgpath)
            theme.append_search_path(imgpath)    
    
        factory = app.get_factory()
        factory.connect('shutdown', app.on_shutdown)
        w = factory.create_initial_window()
        w.new_tab(sys.argv[1:], os.getcwd())
    
        uiproxy = remote.get_proxy(factory)    
 
        w.show_all()
        w.present()
    
        _logger.debug('entering mainloop')
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()    
