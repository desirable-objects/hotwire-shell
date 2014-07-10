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

import os, sys, stat, signal, datetime

import gtk, gobject, pango

from hotwire.logutil import log_except
import hotwire_ui.widgets as hotwidgets
from hotwire_ui.render import ClassRendererMapping, TreeObjectsRenderer

class ListRenderer(TreeObjectsRenderer):
    def __init__(self, *args, **kwargs):
        super(ListRenderer, self).__init__(*args, **kwargs)
        self.__obj = None

    def _setup_view_columns(self):     
        colidx = self._table.insert_column_with_data_func(-1, 'Index',
                                                          hotwidgets.CellRendererText(),
                                                          self.__render_tuple_slice, 0)
        colidx = self._table.insert_column_with_data_func(-1, 'Value',
                                                          hotwidgets.CellRendererText(ellipsize=True),
                                                          self.__render_tuple_slice, 1)
        
    @log_except()
    def __render_tuple_slice(self, col, cell, model, iter, idx):
        tup = model.get_value(iter, 0)
        v = tup[idx]
        valrepr = unicode(repr(v))
        cell.set_property('text', valrepr)
        
    def get_objects(self):
        yield self.__obj
        
    def append_obj(self, o):
        if self.__obj is not None:
            return
        self.__obj = o
        superappend = super(ListRenderer, self).append_obj 
        for i,v in enumerate(o):
            superappend((i, v))

ClassRendererMapping.getInstance().register(list, ListRenderer)
