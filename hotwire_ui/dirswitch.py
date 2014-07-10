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

import os, sys, re, logging, string

import gtk, gobject, pango

from hotwire.state import Preferences
from hotwire.logutil import log_except
import hotwire_ui.widgets as hotwidgets
from hotwire_ui.pixbufcache import PixbufCache
from hotwire.state import History
from hotwire.util import markup_for_match
from hotwire_ui.quickfind import QuickFindWindow

_logger = logging.getLogger("hotwire.ui.DirSwitch")

class DirSwitchWindow(QuickFindWindow):
    def __init__(self):
        super(DirSwitchWindow, self).__init__(_('Switch Directory'))
        self.__selected_dir = None

    def _do_search(self, text):
        hist = History.getInstance()
        text_lower = text.lower()
        for usage in hist.search_dir_usage(text):
            v = usage[0]
            v_lower = v.lower()
            markup = self._markup_search(v, text, v_lower, text_lower)
            if markup is not None:      
                yield (v, markup, 'gtk-directory')
