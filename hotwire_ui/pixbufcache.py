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

import gtk, gobject

from hotwire.externals.singletonmixin import Singleton
from hotwire.async import MiniThreadPool

def _get_datadirs():
    datadir_env = os.getenv('XDG_DATA_DIRS')
    if datadir_env:
        datadirs = datadir_env.split(':')
    else:
        datadirs = ['/usr/share/']
    for d in datadirs:
        yield os.path.join(d, 'hotwire', 'images')
    uninst = os.getenv('HOTWIRE_UNINSTALLED') 
    if uninst:
        yield os.path.join(uninst, 'images')

def _find_in_datadir(fname):
    datadirs = _get_datadirs()
    for dir in datadirs:
        fpath = os.path.join(dir, fname)
        if os.access(fpath, os.R_OK):
            return fpath
    return None

class PixbufCache(Singleton):
    def __init__(self):
        super(PixbufCache, self).__init__()
        self.__cache = {}

    def get(self, path, size=24, animation=False, trystock=False, stocksize=None):
        if trystock:
            pixbuf = self.get_stock(path, size)
            if pixbuf:
                return pixbuf
        if not os.path.isabs(path):
            path = _find_in_datadir(path)
        if not path:
            if path == gtk.STOCK_MISSING_IMAGE:
                return None
            return self.get_stock(gtk.STOCK_MISSING_IMAGE)        
        if not self.__cache.has_key((path, size)):
            pixbuf = self.__do_load(path, size, animation)
            self.__cache[(path, size)] = pixbuf
        return self.__cache[(path, size)]
    
    def get_stock(self, name, size=24):
        if name.find(os.sep) >= 0:
            name = os.path.basename(name)
        (root, ext) = os.path.splitext(name)
        theme = gtk.icon_theme_get_default()
        try:
            return theme.load_icon(name, size, 0)
        except gobject.GError, e:
            return None
        
    def __do_load(self, path, size, animation):
        f = open(path, 'rb')
        data = f.read()
        f.close()
        loader = gtk.gdk.PixbufLoader()
        if size:
            loader.set_size(size, size)
        loader.write(data)
        loader.close()
        if animation:
            return loader.get_animation()
        return loader.get_pixbuf()
