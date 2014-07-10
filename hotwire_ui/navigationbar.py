# This file is part of the Hotwire Shell user interface.
#   
# Copyright (C) 2008 Shixinn Zeng <zeng.shixin@gmail.com>
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

import logging
from xml.sax.saxutils import escape
import  gtk, pango

_logger = logging.getLogger("hotwire_ui.AddressBar")

class BreadButton(gtk.ToggleButton):
    def __init__(self, context, address_bar, path, label=None, **kwargs):
        self.__escaped_dir_name = escape(label)
        super(BreadButton, self).__init__(label = self.__escaped_dir_name, **kwargs)
        self.__context = context
        self.__address_bar = address_bar
        self.__label = self.get_child()
        self.__label.set_ellipsize(pango.ELLIPSIZE_END)
        self.__label.set_use_underline(False)
        self.__label.set_use_markup(True)
        self.__ignore_changes = False
        self.set_focus_on_click(False)
        self.connect('clicked', self.__on_click, path)
        self.__label.connect('size-request', self.__lable_size_request)
        
    def __lable_size_request(self, label, requision):
        layout = label.create_pango_layout(self.__escaped_dir_name)
        layout.set_markup(self.__escaped_dir_name) #this is needed, otherwiser, the width for '&test' is not accurate
        width, height = layout.get_pixel_size()
        
        layout.set_markup("<b>%s</b>" % self.__escaped_dir_name)
        bold_width, bold_height = layout.get_pixel_size()
        
        requision.width = min(150, max(bold_width, width))
        requision.height = max(bold_height, height)
        
    def get_label(self):
        return self.__label.get_text()
    
    def __set_markup(self, text):
        self.__label.set_markup(text)

    def down(self):
        _logger.debug("Down button %s" % self)
        self.__ignore_changes = True
        self.__set_markup("<b>%s</b>" % self.__escaped_dir_name)
        self.set_active(True)
        self.__ignore_changes = False
        
    def up(self):
        _logger.debug("Up button %s" % self)
        self.__ignore_changes = True
        self.__set_markup(self.__escaped_dir_name)
        self.set_active(False)
        self.__ignore_changes = False
        
    def __on_click(self, button, path):
        if self.__ignore_changes:
            return
        children = self.__address_bar.get_children()
        for b in children:
            if b != button:
                self.up()
            else:
                self.down()
        self.__context.do_cd(path)
        
class NavigationBar(gtk.HBox):
    def __init__(self, context, **kwargs):
        super(NavigationBar, self).__init__(**kwargs)
        self.__context = context
        self.__tool_tips = gtk.Tooltips()
        self.__split_cwd()
        _logger.debug('components = ', self.__components)
        self.__append_components(self.__components)
        _logger.debug("initialization finished")

    def refresh(self):
        _logger.debug("refreshing...")
        children = self.get_children()
        self.__split_cwd()
        i = 0
        _logger.debug("childrean = %s", children)
        _logger.debug("Components = %s", self.__components)
        while i < min(len(children), len(self.__components)):
            children[i].up()
            if children[i].get_label() != self.__components[i]:
                break
            i += 1
        if i >= len(self.__components):
            children[i - 1].down()
            for j in xrange(i, len(children)):
                children[j].up()
            return
        for j in xrange(i, len(children)):
            self.remove(children[j])
        self.__append_components(self.__components, i)
        self.get_children()[-1].down()

    def __split_cwd(self):
        cwd = self.__context.get_cwd()
        self.__components = cwd.split('/')
        self.__components[0] += '/'
        self.__components = filter(lambda x: x != '', self.__components)

    def __append_components(self, components, i = 0):
        for j in xrange(i, len(components)):
            b = BreadButton(self.__context, self,
                            components[0] + '/'.join(components[1:j+1]),
                            label = components[j]) 
            self.__tool_tips.set_tip(b, components[j])
            self.pack_start(b, expand = False, fill = False)
            b.show_all()
