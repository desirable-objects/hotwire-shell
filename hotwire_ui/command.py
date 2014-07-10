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

import os, sys, logging, time, inspect, locale, gettext

import gtk, gobject, pango

from hotwire.externals.singletonmixin import Singleton
import hotwire_ui.widgets as hotwidgets
from hotwire_ui.odisp import MultiObjectsDisplay
from hotwire_ui.pixbufcache import PixbufCache
from hotwire.command import CommandQueue
from hotwire.async import QueueIterator
from hotwire.logutil import log_except
from hotwire_ui.oinspect import InspectWindow, ObjectInspectLink, ClassInspectorSidebar
from hotwire.externals.dispatch import dispatcher

_logger = logging.getLogger("hotwire.ui.Command")

class CommandStatusDisplay(gtk.HBox):
    def __init__(self, cmdname):
        super(CommandStatusDisplay, self).__init__(spacing=4)
        self.__cmdname = cmdname
        self.__text = gtk.Label()
        self.pack_start(self.__text, expand=False)
        self.__progress = gtk.ProgressBar()
        self.__progress_visible = False

    def set_status(self, text, progress):
        if self.__cmdname:
            text = self.__cmdname + ' ' + text
        self.__text.set_text(text)
        if progress >= 0:
            if not self.__progress_visible:
                self.__progress_visible = True
                self.pack_start(self.__progress, expand=False)
                self.__progress.show()
            self.__progress.set_fraction(progress/100.0)

class CommandExecutionHeader(gtk.VBox):
    __gsignals__ = {
        "action" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, []),
        "expand-inspector" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),                            
        "setvisible" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, []),
        "complete" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }
    def __init__(self, context, pipeline, odisp, overview_mode=True, **args):
        super(CommandExecutionHeader, self).__init__(**args)
        self.__context = context
        self.__pipeline = pipeline
        self.__overview_mode = overview_mode
        self.__primary_complete = False
        self.__complete_unseen = False
        self.__last_view_time = None
        self.__visible = True
        self.__prev_pipeline_state = None
        self.__cancelled = False
        self.__undone = False
        self.__exception = False
        self.__mouse_hovering = False
        
        self.__throbber_pixbuf_done = PixbufCache.getInstance().get('throbber-done.gif', size=None)
        self.__throbber_pixbuf_ani = PixbufCache.getInstance().get('throbber.gif', size=None, animation=True)
        
        self.__tooltips = gtk.Tooltips()
        
        dispatcher.connect(self.__on_pipeline_state_change, 'state-changed', self.__pipeline)
        dispatcher.connect(self.__on_pipeline_metadata, 'metadata', self.__pipeline)
        
        self.__main_hbox = gtk.HBox()
        self.pack_start(self.__main_hbox, expand=True)
        self.__cmdstatus_vbox = gtk.VBox()
        self.__main_hbox.pack_start(self.__cmdstatus_vbox, expand=True)
        
        self.__titlebox_ebox = gtk.EventBox()
        self.__titlebox_ebox.set_visible_window(False)
        if overview_mode:
            self.__titlebox_ebox.add_events(gtk.gdk.BUTTON_PRESS_MASK
                                            & gtk.gdk.ENTER_NOTIFY_MASK
                                            & gtk.gdk.LEAVE_NOTIFY_MASK)
            self.__titlebox_ebox.connect("enter_notify_event", self.__on_enter) 
            self.__titlebox_ebox.connect("leave_notify_event", self.__on_leave) 
        self.__titlebox_ebox.connect("button-press-event", lambda eb, e: self.__on_button_press(e))

        self.__titlebox = gtk.HBox()
        self.__titlebox_ebox.add(self.__titlebox)
        self.__cmdstatus_vbox.pack_start(hotwidgets.Align(self.__titlebox_ebox), expand=False)
        self.__pipeline_str = self.__pipeline.__str__()
        self.__title = gtk.Label()
        self.__title.set_alignment(0, 0.5)
        #self.__title.set_selectable(True)        
        self.__title.set_ellipsize(True)
        self.__state_image = gtk.Image()
        self.__titlebox.pack_start(self.__state_image, expand=False)
        self.__titlebox.pack_start(hotwidgets.Align(self.__title, padding_left=4), expand=True)
        self.__statusbox = gtk.HBox()
        self.__cmdstatus_vbox.pack_start(self.__statusbox, expand=False)
        self.__status_left = gtk.Label()
        self.__status_right = gtk.Label()
        self.__statusbox.pack_start(hotwidgets.Align(self.__status_left, padding_left=4), expand=False)
        self.__action = hotwidgets.Link()
        self.__action.connect("clicked", self.__on_action)
        self.__statusbox.pack_start(hotwidgets.Align(self.__action), expand=False)          
        self.__statusbox.pack_start(hotwidgets.Align(self.__status_right), expand=False)        
        
        self.__undoable = self.__pipeline.get_undoable() and (not self.__pipeline.get_idempotent())

        status_cmds = list(pipeline.get_status_commands())
        self.__pipeline_status_visible = False
        if status_cmds:
            self.__cmd_statuses = gtk.HBox(spacing=8)
            show_cmd_name = len(status_cmds) > 1
            for cmdname in status_cmds:
                self.__cmd_statuses.pack_start(CommandStatusDisplay(show_cmd_name and cmdname or None), expand=True)
            self.__statusbox.pack_start(hotwidgets.Align(self.__cmd_statuses), expand=False)
        else:
            self.__cmd_statuses = None
            self.__cmd_status_show_cmd = False

        self.__objects = odisp
        self.__objects.connect("primary-complete", self.__on_primary_complete)        
        self.__objects.connect("changed", lambda o: self.__update_titlebox())

        self.__exception_box = gtk.HBox()
        self.__exception_link = hotwidgets.Link()
        self.__exception_link.set_alignment(0.0, 0.5)
        self.__exception_link.set_ellipsize(True)
        self.__exception_link.connect('clicked', self.__on_exception_clicked)
        self.__exception_box.pack_start(self.__exception_link, expand=True)        
        self.__cmdstatus_vbox.pack_start(hotwidgets.Align(self.__exception_box, padding_left=4), expand=False)
        if overview_mode:
            self.__cmdstatus_vbox.pack_start(gtk.HSeparator(), expand=False)
            self.__otype_expander = None
        else:
            self.__otype_expander = gtk.Expander('')
            self.__otype_expander.unset_flags(gtk.CAN_FOCUS);
            self.__otype_expander.set_use_markup(True)
            self.__otype_expander.connect('notify::expanded', self.__on_otype_expander_toggled)
            self.__main_hbox.pack_start(self.__otype_expander, expand=False)
        
    def __on_otype_expander_toggled(self, *args):
        self.emit('expand-inspector', self.__otype_expander.get_property('expanded'))      
        
    def __on_exception_clicked(self, link):
        w = gtk.Dialog(_('Exception - Hotwire'), parent=link.get_toplevel(),
                       flags=0, buttons=(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        w.set_has_separator(False)
        w.set_border_width(5)
        w.set_size_request(640, 480)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        view = gtk.TextView()
        view.set_wrap_mode(True)
        scroll.add(view)
        w.vbox.pack_start(hotwidgets.Border(scroll), expand=True)
        view.get_buffer().set_property('text', self.__pipeline.get_exception_info()[3])
        w.show_all()
        w.run()
        w.destroy()

    def set_inspector_expander_active(self, active):
        self.__otype_expander.set_property('expanded', active)

    def get_pipeline(self):
        return self.__pipeline

    def get_state(self):
        return self.__pipeline.get_state()
    
    def set_unseen(self, unseen):
        self.__complete_unseen = unseen
        _logger.debug("marking %s as unseen=%s", self.__pipeline, unseen)
        self.__update_titlebox()
        
    def update_viewed_time(self):
        self.__last_view_time = time.time()
        
    def get_viewed_time(self):
        return self.__last_view_time        

    def get_visible(self):
        return self.__visible

    def scroll_up(self, full=False):
        if self.__objects:
            self.__objects.scroll_up(full)
        
    def scroll_down(self, full=False):
        if self.__objects:
            self.__objects.scroll_down(full)

    def disconnect(self):
        self.__pipeline.disconnect()

    def get_output_type(self):
        return self.__pipeline.get_output_type()

    def get_output(self):
        # Can't just return objects directly as this can be
        # called from other threads
        # TODO make this actually async
        queue = CommandQueue()
        gobject.idle_add(self.__enqueue_output, queue)
        for obj in QueueIterator(queue):
            yield obj

    def __enqueue_output(self, queue):
        for obj in self.__objects.get_objects():
            queue.put(obj)
        queue.put(None)

    def __on_primary_complete(self, od):
        self.__primary_complete = True
        self.__on_pipeline_state_change(self.__pipeline)
    
    @log_except(_logger)
    def __on_action(self, *args):
        _logger.debug("emitting action")
        self.emit('action')

    def get_objects_widget(self):
        return self.__objects

    def __update_titlebox(self):
        if self.__mouse_hovering:
            self.__title.set_markup('<tt><u>%s</u></tt>' % (gobject.markup_escape_text(self.__pipeline_str),))
        else:
            self.__title.set_markup('<tt>%s</tt>' % (gobject.markup_escape_text(self.__pipeline_str),))
            

        if self.__objects:
            ocount = self.__objects.get_ocount() or 0
            status_str = self.__objects.get_status_str()
            if status_str is None:
                status_str = _('%d objects') % (ocount,)
        else:
            status_str = None
            
        if self.__objects:
            self.__tooltips.set_tip(self.__titlebox_ebox, self.__pipeline_str)      

        def set_status_action(status_text_left, action_text='', status_markup=False):
            if action_text:
                status_text_left += " ("
            if status_text_left:
                if status_markup:
                    self.__status_left.set_markup(status_text_left)
                else:                
                    self.__status_left.set_text(status_text_left)
            else:
                self.__status_left.set_text('')
            if action_text:
                self.__action.set_text(action_text)
                self.__action.show()
            else:
                self.__action.set_text('')
                self.__action.hide()
            status_right_start = action_text and ')' or ''
            status_right_end = self.__pipeline_status_visible and '; ' or ''
            if status_str:
                if status_text_left:
                    status_str_fmt = ', '
                else:
                    status_str_fmt = ''
                status_str_fmt += status_str                
            else:
                status_str_fmt = ''
            self.__status_right.set_text(status_right_start + status_str_fmt + status_right_end)
            
        def _color(text, color):
            return '<span foreground="%s">%s</span>' % (color,gobject.markup_escape_text(text))
        def _markupif(tag, text, b):
            if b:
                return '<%s>%s</%s>' % (tag, text, tag)
            return text
        state = self.get_state()
        if state == 'waiting':
            set_status_action(_('Waiting...'))
        elif state == 'cancelled':
            set_status_action(_markupif('b', _color(_('Cancelled'), "red"), self.__complete_unseen), '', status_markup=True)
        elif state == 'undone':
            set_status_action(_markupif('b', _color(_('Undone'), "red"), self.__complete_unseen), '', status_markup=True)
        elif state == 'exception':
            set_status_action(_markupif('b', _('Exception'), self.__complete_unseen), '', status_markup=True) 
        elif state == 'executing':
            set_status_action(_('Executing'), None)
        elif state == 'complete':
            set_status_action(_markupif('b', _('Complete'), self.__complete_unseen), None, status_markup=True)
        if self.__otype_expander is not None:
            otype = self.__objects.get_output_common_supertype()
            if otype is not None:
                self.__otype_expander.get_property('label-widget').set_markup('<b>%s</b> %s' % (_('Type:'), gobject.markup_escape_text(otype.__name__)))

    def __on_pipeline_metadata(self, cmdidx, cmd, key, flags, meta, sender=None):
        pipeline=sender
        _logger.debug("got pipeline metadata idx=%d key=%s flags=%s", cmdidx, key, flags)
        if key == 'hotwire.fileop.basedir':
            self.__handle_basedir(cmdidx, meta)
            return
        if key == 'hotwire.status':
            self.__handle_status(cmdidx, meta)
            return
        
    def __handle_basedir(self, cmdidx, meta):
        _logger.debug("got basedir %s", meta)
        
    def __handle_status(self, cmdidx, meta):
        self.__pipeline_status_visible = True
        statusdisp = self.__cmd_statuses.get_children()[cmdidx]
        statusdisp.set_status(*meta)
        self.__update_titlebox()

    def __isexecuting(self):
        state = self.__pipeline.get_state()           
        return (state == 'executing' or (state == 'complete' and not self.__primary_complete))
    
    def __on_pipeline_state_change(self, signal=None, sender=None):
        pipeline = sender
        state = self.__pipeline.get_state()        
        _logger.debug("state change to %s for pipeline %s", state, self.__pipeline_str)
        isexecuting = self.__isexecuting()
        self.__update_titlebox()
        if state != 'exception':
            self.__exception_box.hide()                
        if isexecuting:
            self.__state_image.set_from_animation(self.__throbber_pixbuf_ani)
        elif state == 'complete':
            self.__state_image.set_from_pixbuf(self.__throbber_pixbuf_done)            
        elif state == 'cancelled':
            self.__state_image.set_from_stock('gtk-dialog-error', gtk.ICON_SIZE_MENU)
        elif state == 'undone':
            self.__state_image.set_from_stock('gtk-dialog-warning', gtk.ICON_SIZE_MENU)
        elif state == 'exception':
            self.__state_image.set_from_stock('gtk-dialog-error', gtk.ICON_SIZE_MENU)            
            self.__exception_box.show()
            excinfo = self.__pipeline.get_exception_info()
            self.__exception_link.set_text("%s: %s" % (excinfo[0], excinfo[1]))
        else:
            raise Exception("Unknown state %s" % (state,))
        self.emit("complete")

    @log_except(_logger)
    def __on_button_press(self, e):
        if self.__overview_mode and e.button == 1:
            self.emit('setvisible')
            return True
        elif (not self.__overview_mode) and e.button in (1,3):
            menu = gtk.Menu()
            def makemenu(name):
                return self.__context.get_ui().get_action('/Menubar/WidgetMenuAdditions/ControlMenu/' + action).create_menu_item()                
            for action in ['Cancel', 'Undo']:
                menu.append(makemenu(action))
            menu.append(gtk.SeparatorMenuItem())
            menu.append(self.__context.get_ui().get_action('/Menubar/FileMenu/FileDetachAdditions/DetachPipeline').create_menu_item())
            menu.append(gtk.SeparatorMenuItem())
            for action in ['RemovePipeline', 'UndoRemovePipeline']:
                menu.append(makemenu(action))
            menu.show_all()            
            menu.popup(None, None, None, e.button, e.time)                
            return True
        return False

    @log_except(_logger)
    def __on_enter(self, w, c):
        self.__talk_to_the_hand(True)

    @log_except(_logger)
    def __on_leave(self, w, c):
        self.__talk_to_the_hand(False)

    def __talk_to_the_hand(self, hand):
        display = self.get_display()
        cursor = None
        if hand:
            cursor = gtk.gdk.Cursor(display, gtk.gdk.HAND2)
        self.window.set_cursor(cursor)
        self.__mouse_hovering = hand
        self.__update_titlebox()
    
class CommandExecutionDisplay(gtk.VBox):
    def __init__(self, context, pipeline, odisp):
        super(CommandExecutionDisplay, self).__init__()
        self.odisp = odisp
        self.cmd_header = CommandExecutionHeader(context, pipeline, odisp, overview_mode=False)
        self.pack_start(self.cmd_header, expand=False)
        self.pack_start(odisp, expand=True)
        
    def cancel(self):
        self.odisp.cancel()
        self.cmd_header.get_pipeline().cancel()
        
    def undo(self):
        self.cmd_header.get_pipeline().undo()        
    
class CommandExecutionHistory(gtk.VBox):
    __gsignals__ = {
        "show-command" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        "command-action" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),        
    }    
    def __init__(self, context):
        super(CommandExecutionHistory, self).__init__()
        self.__context = context
        self.__cmd_overview = gtk.VBox()
        self.__cmd_overview_scroll = scroll = gtk.ScrolledWindow()
        scroll.set_property('hscrollbar-policy', gtk.POLICY_NEVER)
        scroll.add_with_viewport(self.__cmd_overview)
        self.pack_start(scroll, expand=True)        

    def add_pipeline(self, pipeline, odisp):
        cmd = CommandExecutionHeader(self.__context, pipeline, odisp)
        cmd.connect('action', self.__handle_cmd_action)        
        cmd.show_all()
        cmd.connect("setvisible", self.__handle_cmd_show)        
        self.__cmd_overview.pack_start(cmd, expand=False)
        
    @log_except(_logger)
    def __handle_cmd_action(self, cmd):
        self.emit('command-action', cmd)        
        
    def get_overview_list(self):
        return self.__cmd_overview.get_children()
    
    def remove_overview(self, oview):
        self.__cmd_overview.remove(oview)
        
    def get_scroll(self):
        return self.__cmd_overview_scroll
        
    def scroll_to_bottom(self):
        vadjust = self.__cmd_overview_scroll.get_vadjustment()
        vadjust.value = max(vadjust.lower, vadjust.upper - vadjust.page_size)        
        
    @log_except(_logger)
    def __handle_cmd_show(self, cmd):
        self.emit("show-command", cmd)        
    
class CommandExecutionControl(gtk.VBox):
    # This may be a sucky policy, but it's less sucky than what came before.
    COMPLETE_CMD_EXPIRATION_SECS = 5 * 60
    __gsignals__ = {
        "new-window" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
    }
    __gproperties__ = { 
                       'pipeline-count' : (gobject.TYPE_INT, '', '',
                       0, 4096, 0, gobject.PARAM_READWRITE),
                       'executing-pipeline-count' : (gobject.TYPE_INT, '', '',
                       0, 4096, 0, gobject.PARAM_READWRITE),                       
                       'unseen-pipeline-count' : (gobject.TYPE_INT, '', '',
                       0, 4096, 0, gobject.PARAM_READWRITE)                       
    }
    
    def __init__(self, context):
        super(CommandExecutionControl, self).__init__()

        self.__ui_string = """
<ui>
  <menubar name='Menubar'>
    <menu action='FileMenu'>
      <placeholder name='FileDetachAdditions'>
        <menuitem action='DetachPipeline'/>
      </placeholder>
    </menu>
    <menu action='EditMenu'>
      <placeholder name='EditMenuAdditions'>
        <menuitem action='Copy'/>
        <separator/>
        <menuitem action='Search'/>
        <menuitem action='Input'/> 
      </placeholder>
    </menu>
    <menu action='ViewMenu'>
      <menuitem action='Overview'/>
      <separator/>
      <menuitem action='Inspector'/>
      <separator/>
      <placeholder name='ViewMenuAdditions'/>
      <menuitem action='PreviousCommand'/>
      <menuitem action='NextCommand'/>
      <separator/>
      <menuitem action='PreviousUnseenCommand'/>
      <menuitem action='LastCommand'/>
    </menu>
    <placeholder name='WidgetMenuAdditions'>
      <menu action='ControlMenu'>
        <menuitem action='Cancel'/>
        <menuitem action='Undo'/>
        <separator/>
        <menuitem action='RemovePipeline'/>
        <menuitem action='UndoRemovePipeline'/>                     
      </menu>
    </placeholder>          
  </menubar>
  <accelerator action='ScrollHome'/>
  <accelerator action='ScrollEnd'/>
  <accelerator action='ScrollPgUp'/>
  <accelerator action='ScrollPgDown'/>  
</ui>"""         
        self.__actions = [
            ('DetachPipeline', gtk.STOCK_JUMP_TO, _('Detach _Pipeline'), '<control><shift>N', _('Create window from output'), self.__to_window_cb),                          
            ('Copy', gtk.STOCK_COPY, _('_Copy'), '<control>c', _('Copy output'), self.__copy_cb),                          
            ('Cancel', gtk.STOCK_CANCEL, _('_Cancel'), '<control><shift>c', _('Cancel current command'), self.__cancel_cb),
            ('Undo', gtk.STOCK_UNDO, _('_Undo'), None, _('Undo current command'), self.__undo_cb),            
            ('Search', gtk.STOCK_FIND, _('_Search'), '<control>s', _('Search output'), self.__search_cb),
            ('Input', gtk.STOCK_EDIT, _('_Input'), '<control>i', _('Send input'), self.__input_cb),
            ('ScrollHome', None, _('Output _Top'), '<control>Home', _('Scroll to output top'), self.__view_home_cb),
            ('ScrollEnd', None, _('Output _Bottom'), '<control>End', _('Scroll to output bottom'), self.__view_end_cb), 
            ('ScrollPgUp', None, _('Output Page _Up'), 'Page_Up', _('Scroll output up'), self.__view_up_cb),
            ('ScrollPgDown', None, _('Output Page _Down'), 'Page_Down', _('Scroll output down'), self.__view_down_cb),
            ('ControlMenu', None, _('_Control')),
            ('RemovePipeline', gtk.STOCK_REMOVE, _('_Remove Pipeline'), '<control><shift>K', _('Remove current pipeline view'), self.__remove_pipeline_cb),
            ('UndoRemovePipeline', gtk.STOCK_UNDO, _('U_ndo Remove Pipeline'), '<control><shift>J', _('Undo removal of current pipeline view'), self.__undo_remove_pipeline_cb),            
            ('PreviousCommand', gtk.STOCK_GO_UP, _('_Previous'), '<control>Up', _('View previous command'), self.__view_previous_cb),
            ('NextCommand', gtk.STOCK_GO_DOWN, _('_Next'), '<control>Down', _('View next command'), self.__view_next_cb),
            ('PreviousUnseenCommand', gtk.STOCK_GO_UP, _('Previous _Unseen'), '<control><shift>Up', _('View most recent unseen command'), self.__view_previous_unseen_cb),
            ('LastCommand', gtk.STOCK_GOTO_BOTTOM, _('Last'), '<control><shift>Down', _('View most recent command'), self.__view_last_cb),            
        ]
        self.__toggle_actions = [
            ('Overview', None, _('_Overview'), '<control><shift>o', _('Toggle overview'), self.__overview_cb),
            ('Inspector', None, _('_Inspector'), '<control><shift>I', _('Toggle inspector'), self.__inspector_cb),             
        ]
        self.__action_group = gtk.ActionGroup('HotwireActions')
        self.__action_group.add_actions(self.__actions) 
        self.__action_group.add_toggle_actions(self.__toggle_actions)
        self.__action_group.get_action('Overview').set_active(False)       
        self.__context = context
        
        # Holds a reference to the signal handler id for the "changed" signal on the current odisp
        # so we know when to reload any metadata
        self.__odisp_changed_connection = None
        
        self.__header = gtk.HBox()    
        def create_arrow_button(action_name):
            action = self.__action_group.get_action(action_name)
            icon = action.create_icon(gtk.ICON_SIZE_MENU)
            button = gtk.Button(label='x')
            button.connect('clicked', lambda *args: action.activate())
            action.connect("notify::sensitive", lambda *args: button.set_sensitive(action.get_sensitive()))
            button.set_property('image', icon)
            button.set_focus_on_click(False)            
            return button
        self.__header_label = create_arrow_button('PreviousCommand')
        self.__header.pack_start(self.__header_label, expand=False)
        self.__header_exec_label = gtk.Label()
        self.__header.pack_start(self.__header_exec_label, expand=False)
        self.pack_start(self.__header, expand=False)
        self.__cmd_paned = gtk.HPaned()
        self.pack_start(self.__cmd_paned, expand=True)
        self.__cmd_notebook = gtk.Notebook()
        self.__cmd_paned.pack1(self.__cmd_notebook, resize=True)
        self.__cmd_notebook.connect('switch-page', self.__on_page_switch)
        self.__cmd_notebook.set_show_tabs(False)
        self.__cmd_notebook.set_show_border(False)
        self.__inspector = ClassInspectorSidebar()
        self.__cmd_paned.pack2(self.__inspector, resize=False)
        self.__cmd_overview = CommandExecutionHistory(self.__context)
        self.__cmd_overview.show_all()
        self.__cmd_overview.set_no_show_all(True)
        self.__cmd_overview.connect('show-command', self.__on_show_command)
        self.__cmd_overview.connect('command-action', self.__handle_cmd_overview_action) 
        self.pack_start(self.__cmd_overview, expand=True)
        self.__footer = gtk.HBox()    
        self.__footer_label = create_arrow_button('NextCommand')
        self.__footer.pack_start(self.__footer_label, expand=False)
        self.__footer_exec_label = gtk.Label()
        self.__footer.pack_start(self.__footer_exec_label, expand=False)
        self.pack_start(self.__footer, expand=False)        

        self.__complete_unseen_pipelines = set()
        self.__history_visible = False
        self.__inspector_visible = False
        self.__prevcmd_count = 0
        self.__prevcmd_executing_count = 0
        self.__nextcmd_count = 0
        self.__nextcmd_executing_count = 0
        self.__idle_command_gc_id = 0
        
        self.__actively_destroyed_pipeline_box = []

        self.__sync_visible()
        self.__sync_cmd_sensitivity()
        
    def get_ui(self):
        return (self.__ui_string, self.__action_group, None)
    
    def __get_complete_commands(self):
        for child in self.__iter_cmds():
            if child.get_state() != 'executing':
                yield child
            
    def __iter_cmds(self):
        for child in self.__cmd_notebook.get_children():
            yield child.cmd_header            
     
    def add_cmd_widget(self, cmd):
        pipeline = cmd.cmd_header.get_pipeline()
        dispatcher.connect(self.__on_pipeline_state_change, 'state-changed', pipeline)
        self.__cmd_overview.add_pipeline(pipeline, cmd.odisp)
        pgnum = self.__cmd_notebook.append_page(cmd)
        self.__cmd_notebook.set_current_page(pgnum)
        self.__sync_visible()
        self.__sync_display()
        gobject.idle_add(lambda: self.__sync_display())
        
    def add_pipeline(self, pipeline):
        _logger.debug("adding child %s", pipeline)
        dispatcher.connect(self.__on_pipeline_state_change, 'state-changed', pipeline)
        odisp = MultiObjectsDisplay(self.__context, pipeline) 
        cmd = CommandExecutionDisplay(self.__context, pipeline, odisp)
        cmd.cmd_header.connect('action', self.__handle_cmd_action)
        cmd.cmd_header.connect('expand-inspector', self.__on_expand_inspector)        
        cmd.show_all()
        pgnum = self.__cmd_notebook.append_page(cmd)
        self.__cmd_notebook.set_current_page(pgnum)
        self.__cmd_overview.add_pipeline(pipeline, odisp)
                
        self.__sync_visible()                
        self.__sync_display(pgnum)
                
        self.notify('pipeline-count')                
        # Garbage-collect old commands at this point        
        gobject.idle_add(self.__command_gc)

    @log_except(_logger)
    def __command_gc(self):
        curtime = time.time()
        changed = False
        for cmd in self.__iter_cmds():
            pipeline = cmd.get_pipeline()
            if pipeline in self.__complete_unseen_pipelines:
                continue
            compl_time = pipeline.get_completion_time()
            if not compl_time:
                continue
            lastview_time = cmd.get_viewed_time()            
            if curtime - lastview_time > self.COMPLETE_CMD_EXPIRATION_SECS:
                changed = True
                self.remove_pipeline(pipeline, destroy=True)
                
        for cmdview in self.__actively_destroyed_pipeline_box:
            cmdview.destroy()
        self.__actively_destroyed_pipeline_box = []
        self.__sync_cmd_sensitivity()      

    def __mark_pipeline_unseen(self, pipeline, unseen):
        (cmdview, overview) = self.__get_widgets_for_pipeline(pipeline)
        cmdview.cmd_header.set_unseen(unseen)
        overview.set_unseen(unseen)
        self.notify('unseen-pipeline-count')        

    def __get_widgets_for_pipeline(self, pipeline):
        cmdview, overview = (None, None)
        for child in self.__cmd_notebook.get_children():
            if not child.cmd_header.get_pipeline() == pipeline:
                continue
            cmdview = child
        for child in self.__cmd_overview.get_overview_list():
            if not child.get_pipeline() == pipeline:
                continue
            overview = child
        return (cmdview, overview)
        
    def remove_pipeline(self, pipeline, disconnect=True, destroy=False):
        if disconnect:
            pipeline.disconnect()
        try:
            self.__complete_unseen_pipelines.remove(pipeline)
        except KeyError, e:
            pass
        (cmdview, overview) = self.__get_widgets_for_pipeline(pipeline)
        self.__cmd_notebook.remove(cmdview)
        self.__cmd_overview.remove_overview(overview)
        if destroy:
            cmdview.destroy()
            overview.destroy()
            return None
        self.notify('pipeline-count')        
        return (cmdview, overview)
    
    @log_except(_logger)
    def __handle_cmd_complete(self, *args):
        self.__sync_cmd_sensitivity()
        
    @log_except(_logger)
    def __handle_cmd_overview_action(self, oview, cmd):
        self.__handle_cmd_action(cmd)
        
    @log_except(_logger)
    def __handle_cmd_action(self, cmd):
        pipeline = cmd.get_pipeline()
        _logger.debug("handling action for %s", pipeline)        
        if pipeline.validate_state_transition('cancelled'):
            _logger.debug("doing cancel")
            pipeline.cancel()
        elif pipeline.validate_state_transition('undone'):
            _logger.debug("doing undo")            
            pipeline.undo()                    
        else:
            raise ValueError("Couldn't do action %s from state %s" % (action,cmd.cmd_header.get_pipeline().get_state()))        
      
    @log_except(_logger)        
    def __on_show_command(self, overview, cmd):
        _logger.debug("showing command %s", cmd)
        target = None
        for child in self.__cmd_notebook.get_children():
            if child.cmd_header.get_pipeline() == cmd.get_pipeline():
                target = child
                break
        if target:
            pgnum = self.__cmd_notebook.page_num(target)
            self.__cmd_notebook.set_current_page(pgnum)
            self.__action_group.get_action("Overview").activate()
            from hotwire_ui.shell import locate_current_shell
            hw = locate_current_shell(self)
            hw.grab_focus()
 
    def get_current(self):
        cmd = self.get_current_cmd(full=True)
        return cmd and cmd.odisp
 
    def get_current_cmd(self, full=False, curpage=None):
        if curpage is not None:
            page = curpage
        else:
            page = self.__cmd_notebook.get_current_page()
        if page < 0:
            return None
        cmd = self.__cmd_notebook.get_nth_page(page)
        if full:
            return cmd
        return cmd.cmd_header

    def __copy_cb(self, a):
        _logger.debug("doing copy cmd")
        cmd = self.get_current_cmd(full=True)
        cmd.odisp.do_copy()
    
    def __cancel_cb(self, a):
        _logger.debug("doing cancel cmd")
        cmd = self.get_current_cmd(full=True)
        cmd.cancel()
        
    def __undo_cb(self, a):
        _logger.debug("doing undo cmd")
        cmd = self.get_current_cmd(full=True)
        cmd.undo()        
        
    def __search_cb(self, a):
        cmd = self.get_current_cmd(full=True)
        top = self.get_toplevel()
        lastfocused = top.get_focus()
        cmd.odisp.start_search(lastfocused)
        
    def __input_cb(self, a):
        cmd = self.get_current_cmd(full=True)
        top = self.get_toplevel()
        lastfocused = top.get_focus()
        cmd.odisp.start_input(lastfocused)        
    
    def __view_previous_cb(self, a):
        self.open_output(True)
        
    def __view_next_cb(self, a):
        self.open_output(False)
        
    def __view_previous_unseen_cb(self, a):
        target = None
        for cmd in self.__iter_cmdslice(False):
            pipeline = cmd.odisp.get_pipeline()            
            if pipeline in self.__complete_unseen_pipelines:
                target = cmd
                break
        if target:
            pgnum = self.__cmd_notebook.page_num(target)
            self.__cmd_notebook.set_current_page(pgnum) 
        
    def __view_last_cb(self, a):
        self.__cmd_notebook.set_current_page(self.__cmd_notebook.get_n_pages()-1)
        
    def __view_home_cb(self, a):
        self.__do_scroll(True, True)
        
    def __view_end_cb(self, a):
        self.__do_scroll(False, True)    
        
    def __view_up_cb(self, a):
        self.__do_scroll(True, False)
        
    def __view_down_cb(self, a):
        self.__do_scroll(False, False)
    
    def __to_window_cb(self, a):
        cmd = self.get_current_cmd(full=True)
        pipeline = cmd.cmd_header.get_pipeline()
        #pipeline.disconnect('state-changed', self.__on_pipeline_state_change)                 
        (cmdview, overview) = self.remove_pipeline(pipeline, disconnect=False)
        self.emit('new-window', cmdview)
        self.__sync_display()
        
    def __remove_pipeline_cb(self, a):
        cmd = self.get_current_cmd(full=True)
        pipeline = cmd.cmd_header.get_pipeline()
        _logger.debug("doing remove of %s", pipeline)
        (cmdview, overview) = self.remove_pipeline(pipeline, disconnect=False)
        overview.destroy()
        self.__actively_destroyed_pipeline_box.append(cmdview)        
        self.__sync_display()
        
    def __undo_remove_pipeline_cb(self, a):
        cmd = self.__actively_destroyed_pipeline_box.pop()
        _logger.debug("undoing remove of %s", cmd)        
        pgnum = self.__cmd_notebook.append_page(cmd)
        self.__cmd_notebook.set_current_page(pgnum)
        self.__cmd_overview.add_pipeline(cmd.cmd_header.get_pipeline(), cmd.odisp)
        self.__sync_display(pgnum)

    def __overview_cb(self, a): 
        self.__toggle_history_expanded()
        
    def __on_expand_inspector(self, header, expand):
        if self.__inspector_visible == (not not expand):
            return
        self.__action_group.get_action('Inspector').set_active(expand)
        
    def __inspector_cb(self, a): 
        self.__inspector_visible = not self.__inspector_visible
        self.__sync_inspector_expanded()
        
    def __sync_inspector_expanded(self, nth=None):
        self.__sync_visible()
        curcmd = self.get_current_cmd(True, curpage=nth)
        curcmd.cmd_header.set_inspector_expander_active(self.__inspector_visible)
    
    def __vadjust(self, scroll, pos, full):
        adjustment = scroll.get_vadjustment()
        if not full:
            val = scroll.get_vadjustment().page_increment
            if not pos:
                val = 0 - val;
            newval = adjustment.value + val
        else:
            if pos:
                newval = adjustment.upper
            else:
                newval = adjustment.lower
        newval = max(min(newval, adjustment.upper-adjustment.page_size), adjustment.lower)
        adjustment.value = newval
    
    def __do_scroll(self, prev, full):
        if self.__history_visible:
            scroll = self.__cmd_overview.get_scroll()
            self.__vadjust(scroll, not prev, full)
            return
        cmd = self.get_current_cmd()
        if prev:
            cmd.scroll_up(full)
        else:
            cmd.scroll_down(full)
        
    def __toggle_history_expanded(self):
        self.__history_visible = not self.__history_visible
        _logger.debug("history visible: %s", self.__history_visible)
        self.__sync_visible()
        self.__sync_cmd_sensitivity()
        self.__sync_display()
        if self.__history_visible:
            self.__cmd_overview.scroll_to_bottom()            
        
    def __sync_visible(self):
        if self.__history_visible:
            self.__cmd_overview.show()
            self.__cmd_paned.hide()
            self.__header.hide()
            self.__footer.hide()
        else:
            self.__cmd_overview.hide()
            self.__cmd_paned.show()
            if self.__inspector_visible:
                self.__inspector.show()
            else:
                self.__inspector.hide()
            if self.__nextcmd_count > 0:                
                self.__header.show()
            self.__footer.show()
            
    @log_except(_logger)
    def __on_pipeline_state_change(self, signal=None, sender=None):
        pipeline = sender
        _logger.debug("handling state change to %s", pipeline.get_state())
        if pipeline.is_complete():
            self.__complete_unseen_pipelines.add(pipeline)
            self.__mark_pipeline_unseen(pipeline, True)      
        self.__sync_display()
            
    def __sync_cmd_sensitivity(self, curpage=None):
        actions = map(self.__action_group.get_action, ['Copy', 'Cancel', 'PreviousCommand', 'NextCommand', 'Undo', 
                                                       'Input', 'RemovePipeline', 'DetachPipeline', 
                                                       'PreviousUnseenCommand', 'LastCommand', 'UndoRemovePipeline'])
        if self.__history_visible:
            for action in actions:
                action.set_sensitive(False)
            cmd = None
            return
        else:
            undoidx = 10
            actions[undoidx].set_sensitive(len(self.__actively_destroyed_pipeline_box) > 0)             
            cmd = self.get_current_cmd(full=True, curpage=curpage)
            if not cmd:
                for action in actions[:undoidx]:
                    action.set_sensitive(False)                  
                return
            pipeline = cmd.cmd_header.get_pipeline()   
            _logger.debug("sync sensitivity page %s pipeline: %s", curpage, cmd.cmd_header.get_pipeline().get_state())                
            cancellable = not not (pipeline.validate_state_transition('cancelled'))
            undoable = not not (pipeline.validate_state_transition('undone'))
            _logger.debug("cancellable: %s undoable: %s", cancellable, undoable)
            actions[1].set_sensitive(cancellable)
            actions[4].set_sensitive(undoable)
            actions[5].set_sensitive(pipeline.get_state() == 'executing' and cmd.odisp.supports_input() or False)
            actions[6].set_sensitive(pipeline.is_complete())
            actions[7].set_sensitive(True)
        actions[2].set_sensitive(self.__prevcmd_count > 0)
        actions[3].set_sensitive(self.__nextcmd_count > 0)
        actions[8].set_sensitive(len(self.__complete_unseen_pipelines) > 0)
        npages = self.__cmd_notebook.get_n_pages()
        if curpage is None:
            curpage = self.__cmd_notebook.get_current_page()
        actions[9].set_sensitive(npages > 0 and curpage < npages-1)       
        
    def __sync_display(self, nth=None):
        def set_label(container, label, n, label_exec, n_exec, n_done):
            if n <= 0 or self.__history_visible:
                container.hide_all()
                return
            container.show_all()
            label.set_label(gettext.ngettext(' %d pipeline' % (n,), ' %d pipelines' % (n,), n))
            if n_exec > 0 and n_done > 0:
                label_exec.set_markup(_(' %d executing, <b>%d complete</b>') % (n_exec, n_done))
            elif n_done > 0:
                label_exec.set_markup(_(' <b>%d complete</b>') % (n_done,))
            elif n_exec > 0:
                label_exec.set_label(_(' %d executing') % (n_exec,))
            else:
                label_exec.set_label('')
        # FIXME - this is a bit of a hackish place to put this
        curcmd = self.get_current_cmd(True, curpage=nth)
        if curcmd:
            current = curcmd.cmd_header
            pipeline = current.get_pipeline()
            _logger.debug("sync display, current=%s", pipeline)
            if pipeline in self.__complete_unseen_pipelines:
                self.__complete_unseen_pipelines.remove(pipeline)
                self.__mark_pipeline_unseen(pipeline, False)                
            current.update_viewed_time()
        self.__prevcmd_count = 0
        self.__prevcmd_executing_count = 0
        self.__prevcmd_complete_count = 0
        self.__nextcmd_count = 0
        self.__nextcmd_executing_count = 0
        self.__nextcmd_complete_count = 0
        for cmd in self.__iter_cmdslice(False, nth):
            self.__prevcmd_count += 1
            pipeline = cmd.odisp.get_pipeline()            
            if pipeline.get_state() == 'executing':
                self.__prevcmd_executing_count += 1
            if pipeline in self.__complete_unseen_pipelines:
                self.__prevcmd_complete_count += 1
        for cmd in self.__iter_cmdslice(True, nth):
            self.__nextcmd_count += 1
            pipeline = cmd.odisp.get_pipeline()
            if pipeline.get_state() == 'executing':
                self.__nextcmd_executing_count += 1
            if pipeline in self.__complete_unseen_pipelines:
                self.__nextcmd_complete_count += 1
        self.notify('executing-pipeline-count')                
        # The idea here is to not take up the vertical space if we're viewing the last command.
        if self.__nextcmd_count == 0:
            self.__header.hide()
        else:                
            set_label(self.__header, self.__header_label, self.__prevcmd_count, self.__header_exec_label, self.__prevcmd_executing_count, self.__prevcmd_complete_count)
        set_label(self.__footer, self.__footer_label, self.__nextcmd_count, self.__footer_exec_label, self.__nextcmd_executing_count, self.__nextcmd_complete_count)
        self.__sync_cmd_sensitivity(curpage=nth)        
        
        if curcmd:
            if self.__odisp_changed_connection is not None:
                (o, id) = self.__odisp_changed_connection
                o.disconnect(id)
            odisp = curcmd.odisp
            self.__odisp_changed_connection = (odisp, odisp.connect("changed", self.__sync_odisp))
            self.__sync_odisp(odisp)
        
    @log_except(_logger)
    def __sync_odisp(self, odisp):
        self.__inspector.set_otype(odisp.get_output_common_supertype())        
        
    def __iter_cmdslice(self, is_end, nth_src=None):
        if nth_src is not None:
            nth = nth_src
        else:
            nth = self.__cmd_notebook.get_current_page()
        n_pages = self.__cmd_notebook.get_n_pages()
        if is_end:
            r = xrange(nth+1, n_pages)
        else:
            r = xrange(0, nth)
        for i in r:
            yield self.__cmd_notebook.get_nth_page(i)

    def __on_page_switch(self, notebook, page, nth):
        self.__sync_display(nth=nth)
 
    def open_output(self, do_prev=False, dry_run=False):
        nth = self.__cmd_notebook.get_current_page()
        n_pages = self.__cmd_notebook.get_n_pages()
        _logger.debug("histmode: %s do_prev: %s nth: %s n_pages: %s", self.__history_visible, do_prev, nth, n_pages)
        if do_prev and nth > 0:
            target_nth = nth - 1
        elif (not do_prev) and nth < n_pages-1:
            target_nth = nth + 1
        else:
            return False
        if dry_run:
            return True
        self.__cmd_notebook.set_current_page(target_nth)
        from hotwire_ui.shell import locate_current_shell
        hw = locate_current_shell(self)
        hw.grab_focus()         
        
    def do_get_property(self, property):
        if property.name == 'pipeline-count':
            return self.__cmd_notebook.get_n_pages()
        elif property.name == 'unseen-pipeline-count':
            return len(self.__complete_unseen_pipelines)
        elif property.name == 'executing-pipeline-count':
            return self.__prevcmd_executing_count + self.__nextcmd_executing_count         
        else:
            raise AttributeError('unknown property %s' % property.name)
        
    def create_overview_button(self):
        return OverviewButton(self, self.__action_group.get_action('Overview'))
    
    def create_unseen_button(self):
        return UnseenNotifyButton(self, self.__action_group.get_action('PreviousUnseenCommand'))
        
class OverviewButton(gtk.ToggleButton):
    def __init__(self, outputs, overview_action):
        super(OverviewButton, self).__init__()
        self.__outputs = outputs
        self.__tooltips = gtk.Tooltips()        
        self.__image = gtk.Image()
        self.__image.set_property('pixbuf', PixbufCache.getInstance().get('throbber-done.gif', size=None))        
        self.set_property('image', self.__image)
        self.set_focus_on_click(False)
        outputs.connect('notify::pipeline-count', self.__on_pipeline_count_changed)
        self.__cached_unseen_count = 0
        self.__orig_bg = self.style.bg[gtk.STATE_NORMAL]
        self.__idle_flash_count = 0
        self.__idle_flash_id = 0
        outputs.connect('notify::executing-pipeline-count', self.__on_pipeline_count_changed)                 
        self.__on_pipeline_count_changed()
        
        self.__overview_action = overview_action
        overview_action.connect('notify::active', self.__on_overview_active_changed)
        self.connect('notify::active', self.__on_self_active_changed)
        
    def __on_pipeline_count_changed(self, *args):
        (count, unseen_count, executing_count) = map(self.__outputs.get_property, 
                                                     ('pipeline-count', 'unseen-pipeline-count', 'executing-pipeline-count'))
        self.set_label(_('%d (%d)') % (count, executing_count))
        self.__tooltips.set_tip(self, _('%d total, %d executing, %d complete') % (count, executing_count, unseen_count))         
    
    def __start_idle_flash(self):
        self.__idle_flash_count = 4
        if self.__idle_flash_id == 0:
            self.__idle_flash_id = gobject.timeout_add(250, self.__idle_flash)
            
    @log_except(_logger)
    def __idle_flash(self): 
        self.__idle_flash_count -= 1
        
        if self.__idle_flash_count % 2 == 1:
            self.style.bg[gtk.STATE_NORMAL] = "yellow"
        else:
            self.style.bg[gtk.STATE_NORMAL] = self.__orig_bg
        
        if self.__idle_flash_count == 0:
            self.__idle_flash_id = 0
            return False
        else:
            return True
          
    def __on_self_active_changed(self, *args):
        ostate = self.__overview_action.get_active()
        selfstate = self.get_property('active')
        if ostate != selfstate:
            self.__overview_action.set_active(selfstate)
          
    def __on_overview_active_changed(self, *args):
        self.set_active(self.__overview_action.get_active())
    
class UnseenNotifyButton(gtk.Button):
    def __init__(self, outputs, prevunseen_action):
        super(UnseenNotifyButton, self).__init__()
        self.__tooltips = gtk.Tooltips()        
        self.__image = gtk.Image()
        self.__image.set_from_stock(gtk.STOCK_GO_UP, gtk.ICON_SIZE_MENU)
        self.set_property('image', self.__image)
        self.set_focus_on_click(False)
        self.__outputs = outputs
        outputs.connect('notify::pipeline-count', self.__on_pipeline_count_changed)
        self.__prev_unseen_action = prevunseen_action
        outputs.connect('notify::unseen-pipeline-count', self.__on_pipeline_count_changed)
        self.connect('clicked', self.__on_clicked)

    def __on_pipeline_count_changed(self, *args):
        unseen_count = self.__outputs.get_property('unseen-pipeline-count')
        self.set_label(_('%d complete') % (unseen_count,))              
        if unseen_count > 0:
            self.show()
        else:
            self.hide()
        
    def __on_clicked(self, self2):
        self.__prev_unseen_action.activate()
        self.hide()
