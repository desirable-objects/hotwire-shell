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

import os,sys,platform,logging

import gtk, dbus, dbus.service

import hotwire.sysdep.ipc_impl.dbusutil as dbusutil

_logger = logging.getLogger("hotwire.sysdep.Ipc.DBus")

BUS_NAME = 'org.hotwireshell'
UI_OPATH = '/hotwire/ui'
UI_IFACE = BUS_NAME + '.Ui'

class Ui(dbus.service.Object):
    def __init__(self, factory, bus_name):
        super(Ui, self).__init__(bus_name, UI_OPATH)
        self.__winfactory = factory
        pass

    @dbus.service.method(UI_IFACE,
                         in_signature="u")
    def NewWindow(self, timestamp):
        _logger.debug("Handling NewWindow method invocation (timestamp=%s)", timestamp)
        newwin = self.__winfactory.create_window()
        if timestamp > 0:
            newwin.present_with_time(timestamp)
        else:
            newwin.present()
            
    @dbus.service.method(UI_IFACE,
                         in_signature="usas")            
    def RunTty(self, timestamp, cwd, args):
        self.__winfactory.run_tty(timestamp, cwd, args)      

class IpcDBus(object):
    def __init__(self):
        self.__uiproxy = None

    def singleton(self):
        try:
            _logger.debug("Requesting D-BUS name %s on session bus", BUS_NAME)
            dbusutil.take_name(BUS_NAME, bus=dbus.SessionBus())
        except dbusutil.DBusNameExistsException, e:
            return True
        return False

    def register_window(self, win):
        _logger.debug("Registering window object %s", win)
        bus_name = dbus.service.BusName(BUS_NAME, bus=dbus.SessionBus())
        self.__uiproxy = Ui(win.factory, bus_name)

    def __parse_startup_id(self):
        startup_time = None
        try:
            startup_id_env = os.environ['DESKTOP_STARTUP_ID']
        except KeyError, e:
            startup_id_env = None
        if startup_id_env:
            idx = startup_id_env.find('_TIME')
            if idx > 0:
                idx += 5
                startup_time = int(startup_id_env[idx:])
        return startup_time        

    def new_window(self):
        inst = dbus.SessionBus().get_object(BUS_NAME, UI_OPATH)
        inst_iface = dbus.Interface(inst, UI_IFACE)
        _logger.debug("Sending RaiseNoTimestamp to existing instance")
        try:
            inst_iface.NewWindow(self.__parse_startup_id() or 0) 
        except dbus.DBusException, e:
            _logger.error("Caught exception attempting to send RaiseNoTimestamp", exc_info=True)
            
    def run_tty(self, cwd, *args):
        inst = dbus.SessionBus().get_object(BUS_NAME, UI_OPATH)
        inst_iface = dbus.Interface(inst, UI_IFACE)
        inst.RunTty(self.__parse_startup_id() or 0, cwd, *args)        

def getInstance():
    return IpcDBus()
