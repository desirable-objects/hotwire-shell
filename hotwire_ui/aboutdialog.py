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

from hotwire.sysdep.fs import Filesystem
from hotwire.logutil import log_except
import hotwire.version

_logger = logging.getLogger("hotwire.AboutDialog")

class HotwireAboutDialog(gtk.AboutDialog):
    def __init__(self):
        super(HotwireAboutDialog, self).__init__()
        dialog = self
        dialog.set_property('website', 'http://hotwire-shell.org')
        dialog.set_property('version', hotwire.version.__version__)
        dialog.set_property('authors', ['Colin Walters <walters@verbum.org>'])
        dialog.set_property('copyright', u'Copyright \u00A9 2007,2008 Colin Walters <walters@verbum.org>')
        dialog.set_property('logo-icon-name', 'hotwire')
        dialog.set_property('license', 
                            '''Hotwire is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.\n
Hotwire is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.\n
You should have received a copy of the GNU General Public License
along with Hotwire; if not, write to the Free Software Foundation, Inc.,
51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA''')
        dialog.set_property('name', "Hotwire")
        comments = _("An object-oriented hypershell\n\n")
        if hotwire.version.svn_version_info:
            comments += "changeset: %s\ndate: %s\n" % (hotwire.version.svn_version_info['Revision'], hotwire.version.svn_version_info['Last Changed Date'],)
        dialog.set_property('comments', comments)
