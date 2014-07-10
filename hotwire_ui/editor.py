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

import os, sys, logging, StringIO, traceback, tempfile

import cairo, gtk, gobject, pango

from hotwire.fs import atomic_rename, open_text_file
from hotwire.sysdep.fs import Filesystem, FileStatError
from hotwire.logutil import log_except
from hotwire_ui.aboutdialog import HotwireAboutDialog
from hotwire_ui.inlinesearch import InlineSearchArea

_logger = logging.getLogger("hotwire.Editor")

try:
    try:
        from gtksourceview2 import Buffer as SourceBuffer, View as SourceView
        gtksourceview2_avail = True
    except ImportError, e:
        from gtksourceview import SourceBuffer, SourceView
        gtksourceview2_avail = False
    gtksourceview_avail = True
    _logger.debug("gtksourceview available")
except ImportError, e:
    gtksourceview_avail = False
    _logger.debug("gtksourceview not available")

class GotoLineDialog(gtk.Dialog):
    def __init__(self, parent):
        super(GotoLineDialog, self).__init__(title=_("Go to line"),
                                             parent=parent,
                                             flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                             buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                                      gtk.STOCK_JUMP_TO, gtk.RESPONSE_ACCEPT))
        self.set_default_response(gtk.RESPONSE_ACCEPT)
        self.set_has_separator(False)
        self.set_border_width(5)
        
        self.__vbox = gtk.VBox()
        self.vbox.add(self.__vbox)   
        self.vbox.set_spacing(6)
        self.__entry = gtk.Entry()
        self.__entry.set_activates_default(True)
        self.__vbox.add(self.__entry)
            
    def run_get_line(self):
        self.show_all()
        resp = self.run()
        _logger.debug("got response %r", resp)
        if resp != gtk.RESPONSE_ACCEPT:
            return None
        active = self.__entry.get_text() 
        _logger.debug("got response text %r", active)        
        if not active:
            return None
        return int(active)

class HotEditorWindow(gtk.Window):
    def __init__(self, filename=None, content=None, title=None, parent=None, autosave=False):
        gtk.Window.__init__(self, type=gtk.WINDOW_TOPLEVEL)
        vbox = gtk.VBox()
        self.add(vbox)
        self.__ui_string = """
<ui>
  <menubar name='Menubar'>
    <menu action='FileMenu'>
      <menuitem action='Save'/>
      <menuitem action='SaveAs'/>
      <separator/>
      <menuitem action='ReadOnly'/>
      <separator/>
      <menuitem action='Revert'/>
      <separator/>
      <menuitem action='Close'/>
    </menu>
    <menu action='EditMenu'>
      <menuitem action='Undo'/>
      <menuitem action='Redo'/>
      <separator/>
      <menuitem action='Find'/>
      <menuitem action='GotoLine'/>
    </menu>
    <menu action='ToolsMenu'>
      <menuitem action='About'/>
    </menu>
  </menubar>
</ui>
"""
        self.__create_ui()
        vbox.pack_start(self._ui.get_widget('/Menubar'), expand=False)

        self.__filename = os.path.abspath(filename)
        self.__autosave = autosave
        self.__modified = False
        self.__last_len = 0
         
        self.__save_text_id = 0

        self.gtksourceview_mode = gtksourceview_avail

        if gtksourceview_avail:
            self.input = SourceBuffer()
            self.input_view = SourceView(self.input)
            if gtksourceview2_avail:
                self.input.connect('notify::can-undo', lambda *args: self.__sync_undoredo())
                self.input.connect('notify::can-redo', lambda *args: self.__sync_undoredo())
            else:
                self.input.connect('can-undo', lambda *args: self.__sync_undoredo())
                self.input.connect('can-redo', lambda *args: self.__sync_undoredo())
        else:
            self.input = gtk.TextBuffer()
            self.input_view = gtk.TextView(self.input)
        self.input_view.set_wrap_mode(gtk.WRAP_WORD)
        self.input_view.connect("key-press-event", self.__handle_key_press_event)
        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)        
        scroll.add(self.input_view)
        
        vbox.pack_start(scroll, True, True)

        if filename and os.path.isfile(self.__filename):
            _logger.debug("reading %s", self.__filename)
            f = open_text_file(self.__filename, 'r')
            self.__original_text = f.read()
        else:
            self.__original_text = content
            
        if self.__original_text:
            if gtksourceview_avail:
                self.input.begin_not_undoable_action()
            self.input.set_property('text', self.__original_text)
            self.__last_len = self.input.get_char_count()             
            if gtksourceview_avail:
                self.input.end_not_undoable_action()            
        
        self.input.move_mark_by_name('insert', self.input.get_start_iter())
        self.input.move_mark_by_name('selection_bound', self.input.get_start_iter())
        
        self.input.connect('mark-set', self.__on_mark_set)

        self.__searcharea = InlineSearchArea(self.input_view)
        self.__searcharea.connect('close', self.__on_search_close)
        self.__searcharea.show_all()
        self.__searcharea.hide()
        self.__searcharea.set_no_show_all(True)
        vbox.pack_start(self.__searcharea, expand=False)

        self.__status_hbox = gtk.HBox()
        self.__statusbar = gtk.Statusbar()
        self.__status_hbox.pack_start(self.__statusbar, expand=True)
        self.__statusbar_ctx = self.__statusbar.get_context_id("HotEditor")
        self.__pos_status = gtk.Statusbar()
        self.__pos_status.set_size_request(160, 10) # Taken from GEdit
        self.__pos_context = self.__pos_status.get_context_id("HotEditor")
        self.__status_hbox.pack_start(self.__pos_status, expand=False)
        vbox.pack_start(self.__status_hbox, expand=False)
        self.__sync_undoredo()
        self.__sync_modified_sensitivity()

        self.input.connect("changed", self.__handle_text_changed)

        self.connect("delete-event", self.__handle_delete_event)
        self.__sync_title()
        if parent:
            self.set_transient_for(parent)
        self.set_size_request(800, 600)
        
    def __on_search_close(self, sa):
        self.__searcharea.hide()
        
    def set_read_only(self, readonly):
        readonly_toggle = self.__actiongroup.get_action('ReadOnly')
        readonly_toggle.set_active(readonly)
        
    def set_code_mode(self, codemode):
        if not self.gtksourceview_mode:
            return
        # Non-code is the default
        if not codemode:
            return
        self.input_view.modify_font(pango.FontDescription("monospace"))
        fs = Filesystem.getInstance()
        try:
            mimetype = fs.get_file_sync(self.__filename).mimetype
        except FileStatError, e:
            mimetype = None
        target_lang = None        
        if gtksourceview2_avail:
            import gtksourceview2
            langman = gtksourceview2.language_manager_get_default() 
            for language_id in langman.get_language_ids():
                language = langman.get_language(language_id)
                for langmime in language.get_mime_types():
                    if mimetype == langmime:
                        target_lang = language
                        break
                if target_lang:
                    break
            self.input.set_highlight_syntax(True)
        else:
            import gtksourceview
            target_lang = gtksourceview.SourceLanguagesManager().get_language_from_mime_type(mimetype)
            self.input.set_highlight(True)
        if target_lang:
            self.input.set_language(target_lang)

    def goto_line(self, lineno):
        iter = self.input.get_iter_at_line(lineno)
        self.input.place_cursor(iter)
        
    def __sync_title(self):
        if self.__filename:
            (dn, bn) = os.path.split(self.__filename)
            self.set_title('%s (%s)' % (bn,dn))
        else:
            self.set_title('Untitled')          

    def __show_msg(self, text):
        id = self.__statusbar.push(self.__statusbar_ctx, text)
        gobject.timeout_add(3000, lambda: self.__statusbar.remove(self.__statusbar_ctx, id))        

    def __do_save(self, status):
        if self.__save_text_id > 0:
            gobject.source_remove(self.__save_text_id)
        if not self.__modified:
            self.__show_msg(_("Already saved"))
            return            
        self.__idle_save_text(status)

    @log_except(_logger)
    def __idle_save_text(self, status):
        self.__save_text_id = 0
        _logger.debug("autosaving to %s", self.__filename)
        dn,bn = os.path.split(self.__filename)
        try:
            perms = os.stat(self.__filename).st_mode
        except:
            perms = None
        (tempfd, temppath) = tempfile.mkstemp('.tmp', self.__filename, dn)
        os.close(tempfd)
        f = open_text_file(temppath, 'w')
        text = self.input.get_property("text")
        utext = unicode(text)
        f.write(utext)
        f.flush()
        os.fsync(tempfd)
        f.close()
        if perms is not None:
            os.chmod(temppath, perms)
        atomic_rename(temppath, self.__filename)
        self.__show_msg(status + _("...done"))
        self.__modified = False
        self.__sync_modified_sensitivity()
        _logger.debug("autosave complete")
        return False

    def __handle_key_press_event(self, input_view, event):
        # <Control>Return is the most natural keybinding for save-and-close, but support
        # <Control>w for compat. This doesn't replicate all the complicated multiple-groups
        # handling that would goes on inside GTK+, but that's OK for a compatibility crutch
        if event.state & gtk.gdk.CONTROL_MASK != 0 and event.keyval in (gtk.keysyms.w, gtk.keysyms.W):
            self.__handle_close()
            return True

        if event.keyval == gtk.keysyms.Escape:
            self.__handle_close()
            return True

        return False
    
    def __on_mark_set(self, buf, iter, mark):
        cursor = buf.get_insert()
        if cursor != mark:
            return
        self.__pos_status.pop(self.__pos_context)
        ln = iter.get_line()
        col = iter.get_line_offset()        
        self.__pos_status.push(self.__pos_context, _('Ln %d, Col %d') % (ln, col))
    
    def __handle_text_changed(self, text):
        _logger.debug("handling text changed")
        self.__modified = True
        self.__sync_modified_sensitivity()
        if not (self.__filename and self.__autosave):
            return
        charcount = text.get_char_count()
        # Don't autosave on deletions
        if charcount < self.__last_len:
            return
        self.__last_len = charcount
        if self.__save_text_id != 0:
            gobject.source_remove(self.__save_text_id)
        self.__save_text_id = gobject.timeout_add(15000, self.__idle_save_text, _("Autosaving"))

    @log_except(_logger)
    def __revert_cb(self, action):
        self.__handle_revert()

    def __handle_revert(self):
        self.input.set_property('text', self.__original_text)
        
    @log_except(_logger)        
    def __save_cb(self, action):
        self.__do_save(_("Saving..."))
        
    @log_except(_logger)        
    def __save_as_cb(self, action):
        chooser = gtk.FileChooserDialog(_("Save As..."), self, gtk.FILE_CHOOSER_ACTION_SAVE,
                                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                         gtk.STOCK_SAVE,   gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        response = chooser.run()
        filename = None
        if response == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
        self.__filename = filename
        chooser.destroy()

    def __handle_delete_event(self, w, e):
        return self.__handle_close()

    @log_except(_logger)
    def __close_cb(self, action):
        self.__handle_close()
        
    def __sync_modified_sensitivity(self):
        self.__actiongroup.get_action('Save').set_sensitive(self.__modified)

    @log_except(_logger)
    def __handle_close(self):
        _logger.debug("got close")
        if not self.__modified:
            self.destroy()
        elif self.__filename and self.__autosave:
            self.__save_cb(None)
            self.destroy()   
        else:
            dialog = gtk.MessageDialog(parent=self, buttons=gtk.BUTTONS_NONE,
                                       type=gtk.MESSAGE_QUESTION,
                                       message_format=_("Save changes before closing?"))
            dialog.add_button(_('Close without saving'), gtk.RESPONSE_REJECT)
            dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
            dialog.add_button(gtk.STOCK_SAVE, gtk.RESPONSE_APPLY)            
            dialog.set_default_response(gtk.RESPONSE_CANCEL)
            resp = dialog.run()
            dialog.destroy()
            if resp == gtk.RESPONSE_REJECT:
                self.destroy()
            elif resp == gtk.RESPONSE_CANCEL:
                pass
            elif resp == gtk.RESPONSE_APPLY:
                self.__save_cb(None)
                self.destroy()
        return True                     

    @log_except(_logger)
    def __undo_cb(self, action):
        self.input.undo()

    @log_except(_logger)
    def __redo_cb(self, action):
        self.input.redo()

    def __sync_undoredo(self):
        self.__actiongroup.get_action('Redo').set_sensitive(gtksourceview_avail and self.input.can_redo())
        self.__actiongroup.get_action('Undo').set_sensitive(gtksourceview_avail and self.input.can_undo())
        
    @log_except(_logger)        
    def __search_cb(self, a):
        self.__searcharea.show()
        self.__searcharea.focus()

    @log_except(_logger)        
    def __goto_line_cb(self, a):
        dlg = GotoLineDialog(self)
        line_num = dlg.run_get_line()
        dlg.destroy()        
        if line_num is None:
            return
        iter = self.input.get_iter_at_line(line_num)
        self.input.place_cursor(iter)
        self.input_view.scroll_mark_onscreen(self.input.get_mark('insert')) 
        
    @log_except(_logger)
    def __toggle_read_only_cb(self, a):
        active = a.get_active()
        self.input_view.set_editable(not active)

    def __create_ui(self):
        self.__actiongroup = ag = gtk.ActionGroup('WindowActions')
        actions = [
            ('FileMenu', None, _('_File')),
            ('Save', gtk.STOCK_SAVE, _('_Save'), '<control>s', _('Save to current file'), self.__save_cb),
            ('SaveAs', gtk.STOCK_SAVE, _('Save _As'), '<control><shift>s', _('Save to a new file'), self.__save_as_cb),             
            ('Revert', None, '_Revert', None, _('Revert to saved text'), self.__revert_cb),
            ('Close', gtk.STOCK_CLOSE, _('_Close'), '<control>Return', _('Save and close'), self.__close_cb),
            ('EditMenu', None, '_Edit'),
            ('Undo', gtk.STOCK_UNDO, _('_Undo'), '<control>z', _('Undo previous action'), self.__undo_cb),
            ('Redo', gtk.STOCK_REDO, _('_Redo'), '<control><shift>Z', _('Redo action'), self.__redo_cb),
            ('Find', gtk.STOCK_FIND, _('_Find'), '<control>f', _('Find text'), self.__search_cb),
            ('GotoLine', gtk.STOCK_JUMP_TO, _('_Go to Line'), '<control>l', _('Jump to line number'), self.__goto_line_cb),
            ('ToolsMenu', None, _('_Tools')),                    
            ('About', gtk.STOCK_ABOUT, _('_About'), None, _('About Hotwire'), self.__help_about_cb),            
            ]
        toggle_actions = [
            ('ReadOnly', None, _('Read _Only'), None, _('Toggle read-only mode'), self.__toggle_read_only_cb),                          
        ]
        ag.add_actions(actions)
        ag.add_toggle_actions(toggle_actions)
        self._ui = gtk.UIManager()
        self._ui.insert_action_group(ag, 0)
        self._ui.add_ui_from_string(self.__ui_string)
        self.add_accel_group(self._ui.get_accel_group())

    def __help_about_cb(self, action):
        dialog = HotwireAboutDialog()
        dialog.run()
        dialog.destroy()
