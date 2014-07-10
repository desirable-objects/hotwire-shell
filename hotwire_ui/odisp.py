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

import os,sys,re,Queue,logging,inspect,locale

import gtk, gobject, pango

from hotwire.util import class_is_assignable
from hotwire.command import CommandQueue, Pipeline
from hotwire_ui.render import ClassRendererMapping, DefaultObjectsRenderer
from hotwire.logutil import log_except
import hotwire_ui.widgets as hotwidgets

_logger = logging.getLogger("hotwire.ui.ODisp")

class ObjectsDisplay(gtk.VBox):
    __gsignals__ = {
        "object-input" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        "status-changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),        
    }      
    def __init__(self, output_spec, context, **kwargs):
        super(ObjectsDisplay, self).__init__(**kwargs)
        self.__context = context
        self.__box = gtk.VBox()        
        self.add(self.__box)
        self.__scroll = gtk.ScrolledWindow()
        self.__scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vadjust = self.__scroll.get_vadjustment()
        vadjust.connect('value-changed', self.__on_scroll_value_changed)        
        self.__search = None
        self.__inputarea = None
        self.__output_type = None
        self.__old_focus = None
        self.__box.pack_start(self.__scroll, expand=True)
        self.__display = None
        self.__add_display(output_spec)
        self.__doing_autoscroll = False
        self.__user_scrolled = False
        self.__autoscroll_id = 0
        self._common_supertype = None

    def __add_display(self, output_spec, force=False):
        if output_spec != 'any':
            self.__display = ClassRendererMapping.getInstance().lookup(output_spec, self.__context)
        if not self.__display and force:
            self.__display = DefaultObjectsRenderer(self.__context)        
        if self.__display:
            self.__display.connect('status-changed', self.__on_status_changed)
            self.__display_widget = self.__display.get_widget()
            self.__display_widget.show_all()
            self.__scroll.add(self.__display_widget)
            self.__output_type = output_spec
            
    def __on_status_changed(self, renderer):
        self.emit('status-changed')
        self.do_autoscroll()

    def start_search(self, old_focus):
        try:
            self.__display.start_search()
            return True
        except NotImplementedError, e:
            pass        
        if self.__search is None:
            self.__search = self.__display.get_search()
            if self.__search is not True:
                self.__box.pack_start(self.__search, expand=False)
                self.__search.connect("close", self.__on_search_close)
        self.__old_focus = old_focus
        if self.__search is not True:
            self.__search.show_all()
            self.__search.focus()
            return True
        return False

    def __on_search_close(self, search):
        if self.__search is not True:
            self.__search.hide()
        if self.__old_focus:
            self.__old_focus.grab_focus()
            
    def supports_input(self):
        return self.__display and self.__display.supports_input()
            
    def start_input(self, old_focus):
        if self.__inputarea is None:
            self.__inputarea = self.__display.get_input()
            if self.__inputarea is not True:
                self.__box.pack_start(self.__inputarea, expand=False)
                self.__inputarea.connect("close", self.__on_inputarea_close)
                self.__inputarea.connect("object-input", self.__on_object_input)
        self.__old_focus = old_focus
        if self.__inputarea is not True:
            self.__inputarea.show_all()
            self.__inputarea.focus()

    def __on_object_input(self, ia, obj, *args):
        _logger.debug("got interactive object input: %s", obj)
        self.emit('object-input', obj)

    def __on_inputarea_close(self, search):
        if self.__inputarea is not True:
            self.__inputarea.hide()
        if self.__old_focus:
            self.__old_focus.grab_focus()            
            
    def get_opt_formats(self):
        if self.__display:
            return self.__display.get_opt_formats()
        return []

    def get_status_str(self):
        return self.__display and self.__display.get_status_str()

    def get_objects(self):
        if self.__display:
            for obj in self.__display.get_objects():
                yield obj
        else:
            raise ValueError("Can't get object snapshot, no display")
            
    def get_selected_objects(self):
        if self.__display:
            for obj in self.__display.get_selected_objects():
                yield obj
        else:
            raise ValueError("Can't get object snapshot, no display")            
            
    def get_output_type(self):
        """Return the typespec for the current pipeline.  See Pipeline
        for a description of typespecs."""
        return self.__output_type
                
    def __recurse_get_common_superclass(self, c1, c2):
        for base in c1.__bases__:
            if base == c2:
                return base
            tmp = self.__recurse_get_common_superclass(base, c2)
            if tmp:
                return tmp
        
    def __get_common_superclass(self, c1, c2):
        if c1 == c2:
            return c1
        if isinstance(c2, c1):
            (c1, c2) = (c2, c1)
        elif not isinstance(c1, c2):
            return object
        return self.__recurse_get_common_superclass(c1, c2)        
                
    def get_output_common_supertype(self):
        """Return the common Python supertype inspected from the current stream."""
        return self._common_supertype
                
    def append_object(self, obj, fmt=None, **kwargs):
        if fmt is None:
            otype = type(obj)
        # This is kind of a hack.
        elif fmt in ('bytearray/chunked' 'x-filedescriptor/special'):
            otype = str            
        # If we don't have a display at this point, it means we have a dynamically-typed
        # object stream.  In that case, force the issue and add the default display.
        if not self.__display:
            self.__add_display(otype, force=True)

        # Determine common supertype so we can display it.
        if self._common_supertype is None:
            self._common_supertype = otype
        elif self._common_supertype is not object:
            self._common_supertype = self.__get_common_superclass(otype, self._common_supertype)       
        # Actually append.
        if fmt is not None:
            kwargs['fmt'] = fmt
        self.__display.append_obj(obj, **kwargs)
            
    def __vadjust(self, pos, full, forceuser=False):
        adjustment = self.__scroll.get_vadjustment()
        if not full:
            val = self.__scroll.get_vadjustment().page_increment
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

    def __on_scroll_value_changed(self, vadjust):
        upper = vadjust.upper - vadjust.page_size
        if upper - vadjust.value < (vadjust.page_size/3):
            self.__user_scrolled = False
        else:
            self.__user_scrolled = True         

    def scroll_up(self, full, forceuser=True):
        self.__vadjust(False, full)
        
    def scroll_down(self, full, forceuser=True):
        self.__vadjust(True, full)
        
    def do_copy(self):
        if self.__display:
            return self.__display.do_copy()
        return False

    def __idle_do_autoscroll(self):
        vadjust = self.__scroll.get_vadjustment()
        vadjust.value = max(vadjust.lower, vadjust.upper - vadjust.page_size)
        self.__autoscroll_id = 0

    def do_autoscroll(self):
        if self.__display and self.__display.get_autoscroll():
            if not self.__user_scrolled:
                if self.__autoscroll_id == 0:
                    self.__autoscroll_id = gobject.timeout_add(150, self.__idle_do_autoscroll)

class MultiObjectsDisplay(gtk.Notebook):
    __gsignals__ = {
        "primary-complete" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        "changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }
        
    def __init__(self, context, pipeline):
        super(MultiObjectsDisplay, self).__init__()
        self.__context = context
        self.__pipeline = pipeline
        self.__cancelled = False
        self.__default_odisp = None
        self.__queues = {}
        self.__ocount = 0
        self.__do_autoswitch = True
        self.__suppress_noyield = not not list(pipeline.get_status_commands())
        self.set_show_tabs(False)

        self.__inputqueue = None
        intype = self.__pipeline.get_input_type()
        _logger.debug("input type %s opt: %s", intype, self.__pipeline.get_input_optional())
        # FIXME assume for the moment we can only input strings; also explicitly avoid allowing input for 'any'
        # Long term we might consider only allowing input for SysBuiltin.
        if intype not in (None, 'any') and Pipeline.streamtype_is_assignable(intype, str, False) and self.__pipeline.get_input_optional():
            self.__inputqueue = CommandQueue()
            self.__pipeline.set_input_queue(self.__inputqueue)
        self.append_ostream(pipeline.get_output_type(), None, pipeline.get_output(), False)
        for aux in pipeline.get_auxstreams():
            self.append_ostream(aux.schema.otype, aux.name, aux.queue, aux.schema.merge_default)

    def start_search(self, old_focus):
        self.__default_odisp.start_search(old_focus)

    def supports_input(self):
        return self.__default_odisp and self.__default_odisp.supports_input()

    def start_input(self, old_focus):
        self.__default_odisp.start_input(old_focus)

    def do_copy(self):
        return self.__default_odisp.do_copy()

    def get_opt_formats(self):
        if self.__default_odisp:
            return self.__default_odisp.get_opt_formats()
        return []

    def get_pipeline(self):
        return self.__pipeline

    def get_output_common_supertype(self):
        if self.__default_odisp:
            return self.__default_odisp.get_output_common_supertype()
        return None
    
    def make_snapshot(self, selected=False):
        odisp = self.__default_odisp
        if selected:
            objs = self.__default_odisp.get_selected_objects()
        else:          
            objs = self.__default_odisp.get_objects()
        # snapshot it - FIXME this should really be async
        objs = list(objs)      
        if self.__pipeline.is_singlevalue:
            return objs[0]
        return objs

    def append_ostream(self, otype, name, queue, merged):
        label = name or ''
        if merged:
            odisp = self.__default_odisp
        elif not (otype is None):
            odisp = ObjectsDisplay(otype, self.__context) 
            if name is None:
                self.__default_odisp = odisp
                odisp.connect('object-input', self.__on_object_input)
                odisp.connect('status-changed', self.__on_status_change)                
                self.__default_odisp
                self.insert_page(odisp, position=0)
                self.set_tab_label_text(odisp, name or 'Default')
                odisp.show_all()
        elif not self.__suppress_noyield:
            self.__noobjects = gtk.Label()
            self.__noobjects.set_alignment(0, 0)
            self.__noobjects.set_markup('<i>(Pipeline yields no objects)</i>')
            self.__noobjects.show()
            self.insert_page(self.__noobjects, position=0)
            odisp = None
        else:
            odisp = None
        self.__queues[queue] = (odisp, name, merged)
        queue.connect(self.__idle_handle_output, priority=gobject.PRIORITY_LOW)

    def cancel(self):
        self.__cancelled = True
        for queue in self.__queues.iterkeys():
            queue.disconnect()

    def get_ocount(self):
        return self.__ocount

    def get_status_str(self):
        return self.__default_odisp and self.__default_odisp.get_status_str()
    
    def get_default_output_type(self):
        return self.__default_odisp and self.__default_odisp.get_output_type()
    
    def __on_object_input(self, odisp, obj):
        self.__inputqueue.put(obj)
        
    def __on_status_change(self, odisp):
        self.emit("changed")
        
    def __idle_handle_output(self, queue):
        if self.__cancelled:
            _logger.debug("cancelled")
            return False
        empty = False
        changed = False
        (odisp, name, merged) = self.__queues[queue]
        odisp_displayed = odisp in self.get_children()
        active_odisp = False
        maxitems = 100
        i = 0
        append_kwargs = {}
        if queue.opt_type:
            append_kwargs['fmt'] = queue.opt_type
        try:
            while i < maxitems:
                i += 1
                item = queue.get(False)
                changed = True
                if item is None:
                    if name is None:
                        self.emit("primary-complete")
                    empty = True
                    queue.disconnect()
                    break
                _logger.debug("appending item: %s", item)
                if odisp:
                    if not odisp_displayed:
                        self.append_page(odisp)
                        odisp.show_all()
                        self.set_tab_label_text(odisp, name or 'Default')
                        self.set_show_tabs(True)
                        odisp_displayed = True
                    odisp.append_object(item, **append_kwargs)
                    self.__ocount += 1
                    if self.__do_autoswitch:
                        self.set_current_page(self.page_num(odisp))
                        self.__do_autoswitch = False
                    active_odisp = True
                else:
                    _logger.warn("Unexpected item %s from queue %s", item, name)
        except Queue.Empty:
            pass
        if empty:
            del self.__queues[queue]
        if active_odisp:
            odisp.do_autoscroll()
        if changed:
            self.emit("changed")
        readd_idle = (not empty) and (i == maxitems)
        _logger.debug("doing idle readd: %s", readd_idle)
        return readd_idle

    def scroll_up(self, full=False):
        self.get_nth_page(self.get_current_page()).scroll_up(full)
        
    def scroll_down(self, full=False):
        self.get_nth_page(self.get_current_page()).scroll_down(full)

