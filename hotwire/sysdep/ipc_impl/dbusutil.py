# This file is part of the Hotwire Shell project API.

# Copyright (C) 2007 Colin Walters <walters@verbum.org>

# Permission is hereby granted, free of charge, to any person obtaining a copy 
# of this software and associated documentation files (the "Software"), to deal 
# in the Software without restriction, including without limitation the rights 
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies 
# of the Software, and to permit persons to whom the Software is furnished to do so, 
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all 
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE X CONSORTIUM BE 
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, 
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR 
# THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import dbus, dbus.glib

def bus_proxy(bus=None):
    target_bus = bus or dbus.Bus()
    return target_bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')

class DBusNameExistsException(Exception):
    pass

def take_name(name, replace=False, on_name_lost=None, bus=None):
    target_bus = bus or dbus.Bus()
    proxy = bus_proxy(bus=target_bus)
    flags = 1 | 4 # allow replacement | do not queue
    if replace:
        flags = flags | 2 # replace existing
    if not proxy.RequestName(name, dbus.UInt32(flags)) in (1,4):
        raise DBusNameExistsException("Couldn't get D-BUS name %s: Name exists")
    if on_name_lost:
        proxy.connect_to_signal('NameLost', on_name_lost)
