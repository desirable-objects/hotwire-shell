It is recommended to install packages for your operating system:
http://code.google.com/p/hotwire-shell/wiki/HotwireUnixLinux

But if you want to run from source, just run this command:

python ui/hotwire

See http://code.google.com/p/hotwire-shell/wiki/BuildingFromSubversion
for more information.  You can easily create a launcher from your
desktop panel to run Hotwire straight from the source.

If you insist on installing to the OS system, you can do it thus:

sudo setup.py install
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor

In the future the second step will be integrated into the setup.py process.
