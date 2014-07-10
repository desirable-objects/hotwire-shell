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

import os, stat, signal, datetime

import gtk, gobject, pango

import hotwire
import hotwire_ui.widgets as hotwidgets
from hotwire_ui.renderers.file import FilePathRenderer
from hotwire_ui.render import ClassRendererMapping, TreeObjectsRenderer
from hotwire.builtins.fsearch import FileStringMatch
from hotwire.util import markup_for_match

class FileStringMatchRenderer(TreeObjectsRenderer):
    def __init__(self, *args, **kwargs):
        super(FileStringMatchRenderer, self).__init__(*args,
                                                      **kwargs)

    def _setup_view_columns(self):
        self._insert_column('path', title=_('Path'))
        self._insert_column('line_num', title=_('Line'))        
        colidx = self._table.insert_column_with_data_func(-1, 'Match',
                                                          hotwidgets.CellRendererText(),
                                                          self._render_match)
        col = self._table.get_column(colidx-1)
        col.set_spacing(0)

    def _render_match(self, col, cell, model, iter):
        obj = model.get_value(iter, 0)
        matchmarkup = markup_for_match(obj.line, obj.match_start, obj.match_end)
        cell.set_property('markup', matchmarkup)

ClassRendererMapping.getInstance().register(FileStringMatch, FileStringMatchRenderer)
