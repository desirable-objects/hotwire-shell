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

from hotwire_ui.render import ClassRendererMapping, TreeObjectsRenderer, menuitem
from hotwire.sysdep.proc import Process

class ProcessRenderer(TreeObjectsRenderer):
    def _setup_view_columns(self):
        self._insert_propcol('pid', title=_('PID'), ellipsize=False)
        self._insert_proptext('owner_name', title=_('Owner'), ellipsize=False)
        cmdcol = self._insert_proptext('cmd', title=_('Command'), ellipsize=False)
        self._set_search_column(cmdcol)

    @menuitem()
    def kill(self, iter):
        proc = self._model.get_value(iter, 0)
        proc.kill()

ClassRendererMapping.getInstance().register(Process, ProcessRenderer)
