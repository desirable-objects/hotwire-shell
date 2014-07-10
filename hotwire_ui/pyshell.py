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

import os, sys, logging, StringIO, traceback

import cairo, gtk, gobject, pango

from hotwire_ui.editor import HotEditorWindow

_logger = logging.getLogger("hotwire.PyShell")

class OutputWindow(gtk.Window):
    def __init__(self, content, parent=None):
        super(OutputWindow, self).__init__(gtk.WINDOW_TOPLEVEL)
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
        self.output = gtk.TextBuffer()
        self.output_view = gtk.TextView(self.output)
        self.output_view.set_wrap_mode(gtk.WRAP_WORD)
        self.output_view.set_property("editable", False)
        self.output.set_property('text', content)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        scroll.add(self.output_view)
        vbox.pack_start(scroll, True, True)
        if parent:
            self.set_transient_for(parent)
        self.set_size_request(640, 480)      
        
    def __create_ui(self):
        self.__actiongroup = ag = gtk.ActionGroup('OutputWindowActions')
        actions = [
            ('FileMenu', None, 'File'),
            ('Close', gtk.STOCK_CLOSE, '_Close', 'Return', 'Close window', self.__close_cb),
            ]
        ag.add_actions(actions)
        self._ui = gtk.UIManager()
        self._ui.insert_action_group(ag, 0)
        self._ui.add_ui_from_string(self.__ui_string)
        self.add_accel_group(self._ui.get_accel_group()) 
        
    def __close_cb(self, action):
        self.destroy()               
        
class CommandShell(HotEditorWindow):
    DEFAULT_CONTENT = '''## Hotwire Python Pad
## Global values:
##   outln(val): (Function) Print a value and a newline to output stream
##   inspect(val): (Function) Display object in visual object inspector
##   curshell(): (Function) Get current Hotwire object 
##   
import os,sys,re
import gtk, gobject

outln('''
    def __init__(self, locals={}, savepath=None, content=None, parent=None):
        super(CommandShell, self).__init__(content=(content or self.DEFAULT_CONTENT), filename=savepath, parent=parent)
        self._locals = locals
        self.__ui_string = """
<ui>
  <menubar name='Menubar'>
    <menu action='ToolsMenu'>
      <menuitem action='Eval'/>    
      <separator/>
      <menuitem action='Reset'/>
    </menu>
  </menubar>
</ui>        
"""    
        actions = [
            ('ToolsMenu', None, 'Tools'),
            ('Eval', None, '_Eval', '<control>Return', 'Evaluate current input', self.__eval_cb),            
            ('Reset', None, '_Reset', None, 'Reset to default content', self.__reset_cb),
            ]
        self.__actiongroup = ag = gtk.ActionGroup('ShellActions')        
        ag.add_actions(actions)
        self._ui.insert_action_group(ag, 1)
        self._ui.add_ui_from_string(self.__ui_string)

        if self.gtksourceview_mode:
            try:
                import gtksourceview2
                pylang = gtksourceview2.language_manager_get_default().get_language('python')
            except ImportError, e:
                import gtksourceview
                pylang = gtksourceview.SourceLanguagesManager().get_language_from_mime_type("text/x-python")
                self.input.set_highlight(True)
            self.input.set_language(pylang)
            
        # Doesn't make sense when we're not backed by a file
        self._ui.get_action_groups()[0].get_action('Revert').set_sensitive(False)
            
        self.input.move_mark_by_name("insert", self.input.get_end_iter())
        self.input.move_mark_by_name("selection_bound", self.input.get_end_iter())        
            
        self.set_title('Hotwire Command Shell')
        self.input_view.modify_font(pango.FontDescription("monospace"))        

    def __do_inspect(self, o):
        from hotwire_ui.oinspect import InspectWindow
        w = InspectWindow(o)
        w.show_all()

    def __eval_cb(self, a):
        try:
            output_stream = StringIO.StringIO()
            text = self.input.get_property("text")
            code_obj = compile(text, '<input>', 'exec')
            locals = {}
            for k, v in self._locals.items():
                locals[k] = v
            locals['output'] = output_stream
            locals['outln'] = lambda v: self.__outln(output_stream, v)
            locals['inspect'] = self.__do_inspect
            exec code_obj in locals
            _logger.debug("execution complete with %d output characters" % (len(output_stream.getvalue())),)
            output_str = output_stream.getvalue()
            if output_str:
                owin = OutputWindow(output_str, parent=self)
                owin.show_all()
        except:
            _logger.debug("caught exception executing", exc_info=True)
            owin = OutputWindow(traceback.format_exc(), parent=self)
            owin.show_all()
            
    def __reset_cb(self, a):
        self.input.set_property('text', self.DEFAULT_CONTENT)
            
    def __outln(self, stream, v):
        stream.write(str(v))
        stream.write('\n')
