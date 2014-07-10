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

import os,sys,logging
import xml.sax, xml.sax.handler

import cairo, gtk, gobject, pango

_logger = logging.getLogger("hotwire.Widgets")

class Link(gtk.EventBox):
    __gsignals__ = {
        "clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }
    
    def __init__(self,**kwargs):
        super(Link, self).__init__(**kwargs)
        self.set_visible_window(False)
        self.__text = None
        self.__label = gtk.Label()
        self.add(self.__label)
        self.connect("button-press-event", self.__on_button_press)
        self.connect("enter_notify_event", self.__on_enter) 
        self.connect("leave_notify_event", self.__on_leave) 
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK
                        & gtk.gdk.ENTER_NOTIFY_MASK
                        & gtk.gdk.LEAVE_NOTIFY_MASK)

    def set_alignment(self, x, y):
        self.__label.set_alignment(x, y)
        
    def set_ellipsize(self, do_ellipsize):
        self.__label.set_ellipsize(do_ellipsize)

    def __on_button_press(self, self2, e):
        if e.button == 1:
            self.emit("clicked")
            return True
        return False

    def get_text(self):
        return self.__text
    
    def set_text(self, text):
        self.__text = text
        self.set_markup(gobject.markup_escape_text(text))
        
    def set_markup(self, text):
        self.__label.set_markup('<span foreground="blue">%s</span>' % (text,))

    def __on_enter(self, w, c):
        self.__talk_to_the_hand(True)

    def __on_leave(self, w, c):
        self.__talk_to_the_hand(False)

    def __talk_to_the_hand(self, hand):
        display = self.get_display()
        cursor = None
        if hand:
            cursor = gtk.gdk.Cursor(display, gtk.gdk.HAND2)
        self.window.set_cursor(cursor)

class Align(gtk.Alignment):
    def __init__(self, child, padding_left=0, padding_right=0, padding_top=0, padding_bottom=0,
                 xalign=0.0, xscale=1.0, yalign=0.5, yscale=1.0):
        super(Align, self).__init__()
        self.set(xalign, yalign, xscale, yscale)
        self.add(child)
        self.set_padding(padding_top, padding_bottom, padding_left, padding_right)

class Border(gtk.Frame):
    def __init__(self, child, label=None, shadow=gtk.SHADOW_ETCHED_IN):
        super(Border, self).__init__(label)
        self.add(child)
        self.set_shadow_type(shadow)

# FIXME this widget is a towering pile of hacks.  The goal is to:
# - keep window positioned above the entry at all times
# - grow up (gravity should solve this)
#
# On Linux/X11, setting our gravity gets us mostly there, but
# there appears to be a race where sometimes our size allocation
# is wrong (?), and so the height position allocations are off.
#
# On Windows, gravity appears not to work at all.  Thus, essentially
# what we rely on is the calling code invoking reposition() every time
# a change that could affect the window size occurs.  Yes, this blows!
# It inevitably causes flickering movement occasionally.  There
# might be a way to avoid the manual nature of it by hooking into
# some point in the size request chain.
#
# Talking with Owen Taylor, this bug is relevant:
# http://bugzilla.gnome.org/show_bug.cgi?id=362383
# see also http://svn.mugshot.org/dumbhippo/trunk/client/linux/src/hippo-window-gtk.c
class TransientPopup(gtk.Window):
    def __init__(self, ref_widget, ref_window, orient='top'):
        super(TransientPopup, self).__init__(gtk.WINDOW_POPUP)
        self.__ref_widget = ref_widget

        self.__spacing = 10

        self.set_resizable(False)
        self.set_screen(ref_widget.get_screen())

        self.__shown = False
        self.__idle_reposition_id = 0        
        self.__configure_connected = False

        self.set_transient_for(ref_window)
        self.set_destroy_with_parent(True)

        self.__box = gtk.VBox()
        self.__border = Border(self.__box)
        self.__border.show_all()
        self.add(self.__border)
        self.set_default(None)
        self.set_decorated(False)
        self.set_focus_on_map(False)
        self.set_focus(None)
        # we wish we could do this, but it doens't work on Windows right now
        #self.set_gravity(gtk.gdk.GRAVITY_SOUTH_WEST)
        self.unset_flags(gtk.CAN_FOCUS)

    def __on_refwin_destroy(self, refw):
        self.destroy()

    def reposition(self):
        if not self.__ref_widget.window:
            return
        (x, y) = self.__ref_widget.window.get_origin()
        alloc = self.__ref_widget.get_allocation()
        (w, h) = self.size_request()
        (parent_w, parent_h) = self.__ref_widget.get_toplevel().get_size()
        move_x = x
        move_y = y - h
        (cur_x, cur_y) = self.get_position()
        _logger.debug("move: x: %d y: %d ax: %d ay: %d ah: %d pw: %d ph:%d h: %d (target: %d %d current: %d %d)",
                      x, y, alloc.x, alloc.y, alloc.height, parent_w, parent_h, h, move_x, move_y,
                      cur_x, cur_y)
        if (cur_x != move_x) or (cur_y != move_y):
            self.move(move_x, move_y)

    # override
    def do_size_request(self, req):
        (req.width, req.height) = self.__border.size_request()
        #(parent_w, parent_h) = map(lambda x: int(x*0.8), self.__ref_widget.get_toplevel().get_size())
        (ref_x, ref_y, ref_w, ref_h, bits) = self.__ref_widget.get_parent_window().get_geometry()
        req.width = min(int(0.8*ref_w), req.width)
        req.height = min(int(0.8*ref_h), req.height)

    def queue_reposition(self):
        if self.__idle_reposition_id > 0:
            return
        self.__idle_reposition_id = gobject.idle_add(self.__idle_reposition)

    def __idle_reposition(self):
        self.reposition()
        self.__idle_reposition_id = 0
        return False            

    def __on_ref_configure(self, refw, event):
        _logger.debug("got ref configure")
        self.reposition()

    def hide(self):
        self.__shown = False
        super(TransientPopup, self).hide()

    def show(self):
        if self.__shown:
            return
        self.__shown = True
        if not self.__configure_connected:
            self.__configure_connected = True
            self.__ref_widget.get_toplevel().connect("configure-event", self.__on_ref_configure)
        self._set_size_request()
        self.reposition()
        self.show_all()        
            
    def _set_size_request(self):
        pass

    def get_box(self):
        return self.__box
gobject.type_register(TransientPopup)

# not finished attempt to do a link with cursor changes on mouseenter
# need to create event box, finish implementing render()
## class CellRendererLink(gtk.CellRenderer):
##     def __init__(self):
##         self.set_property('xalign', 0.0)
##         self.set_property('yalign', 0.5)
##         self.set_property('xpad', 2)
##         self.set_property('ypad', 2)
##         self.__ellipsize = True
##         self.__text = text
        
##     def render(self, drawable, widget, bg, area, expose, flags):
##         layout = self.widget.create_pango_layout(self.__text)
##         attrs = pango.AttrList()
##         attrs.insert(pango.AttrForeground(0, 0, 0xAAAA, 3000))
##         layout.set_ellipsize(self.__ellipsize)
##         layout.set_wrap(False)

class CellRendererText(gtk.CellRendererText):
    """This class takes keyword arguments, in contrast to the GTK+ one."""
    def __init__(self, **kwargs):
        super(CellRendererText, self).__init__()
        for k,v in kwargs.iteritems():
            self.set_property(k.replace('_', '-'), v)
        
class CellRendererLink(CellRendererText):
    __gsignals__ = {
        "clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }
    
    def __init__(self, underline=pango.UNDERLINE_SINGLE, **kwargs):
        super(CellRendererLink, self).__init__(mode=gtk.CELL_RENDERER_MODE_ACTIVATABLE,
                                               foreground_gdk=gtk.gdk.color_parse("blue"),
                                               underline=underline, **kwargs) 
    def set_text(self, text):
        self.set_property('text', text)

    def activate(self, event, widget, path, bg, area, flags):
        if event.button == 1:
            self.emit("clicked")


class BasicMarkupHandler(xml.sax.handler.ContentHandler):
    def __init__(self, buf):
        xml.sax.handler.ContentHandler.__init__(self)
        self.__buf = buf
        self.__curtags = []

    def startElement(self, name, attrs):
        if name == 'basicmarkup':
            return
        self.__curtags.append(str(name))

    def __insert(self, text):
        self.__buf.insert_with_tags_by_name(self.__buf.get_iter_at_mark(self.__buf.get_insert()), text, *self.__curtags)

    def characters(self, text):
        self.__insert(text)

    def ignorableWhitespace(self, text):
        self.__insert(text)

    def endElement(self, name):
        if name == 'basicmarkup':
            return
        self.__curtags.pop()

class BasicMarkupTextBuffer(gtk.TextBuffer):
    def __init__(self):
        super(BasicMarkupTextBuffer, self).__init__()
        self.create_tag('tt', family='Monospace')
        self.create_tag('i', style=pango.STYLE_ITALIC)
        self.create_tag('larger', scale=pango.SCALE_LARGE)
        self.create_tag('b', weight=pango.WEIGHT_BOLD)
        self.create_tag('red', foreground="red")
        self.create_tag('link', foreground="blue", underline=pango.UNDERLINE_SINGLE)

    def insert_markup(self, markup):
        xml.sax.parseString('<basicmarkup>' + markup + '</basicmarkup>', BasicMarkupHandler(self))
                

## class FlowTable(gtk.Container):
##     def __init__(self, spacing=6):
##         super(FlowTable, self).__init__()
##         self.__children = []
##         self.__spacing = spacing

##     def do_add(self, widget):
##         self.__children.append(widget)
##         widget.set_parent(self)

##     def do_size_request(self):
##         w = 0
##         h = 0
##         child_requests = map(lambda c: c.size_request(), self.__children)
##         for child_w, child_h in child_requests:
##             if child_h > h:
##                 h = child_h
##             w += (child_w + self.__spacing)
##         if w > 0:
##             w -= self.__spacing
##         self.__requisition = (w,h)
##         return (w, h)

##     def do_size_allocate(self, allocation):
##         self.allocation = allocation

##         child_requisitions = map(lambda c: c.get_child_requisition(), self.__children)
##         max_w = 0
##         for child_w, child_h in child_requisitions:
##             max_w = max(max_w, child_w)
##         reqs_by_size = list(child_requisitions)
##         reqs_by_size.sort(lambda a,b: cmp(b[0],a[0]))
##         avail_width = allocation.width
##         max_cols = 0
##         for req in reqs_by_size:
##             if req.width >= avail_width:

##         cols = []
##         if max_w >= self.allocation.width:
##             n_cols = 1
##         else:
##             current_col_width = 0
##             for child_w, child_h in child_requisitions:
##                 if current_col_width + child_w > allocation.width:

## gobject.type_register(FlowTable)
                
