"""distutils_extra.command.build_help

Implements the Distutils 'build_help' command."""

import distutils
import glob
import os
import os.path
import re
import sys
import distutils.command.build

class build_help(distutils.cmd.Command):

    description = "install a docbook based documentation"

    user_options= [('help_dir', None, 'help directory of the source tree')]

    def initialize_options(self):
        self.help_dir = None

    def finalize_options(self):
        if self.help_dir is None:
            self.help_dir = os.path.join("help")

    def run(self):
        data_files = self.distribution.data_files

        self.announce("Setting up help files...")
        for filepath in glob.glob("help/*"):
            lang = filepath[len("help/"):]
            self.announce(" Language: %s" % lang)
            path_xml = os.path.join("share/gnome/help",
                                    self.distribution.metadata.name,
                                    lang)
            path_figures = os.path.join("share/gnome/help",
                                        self.distribution.metadata.name,
                                        lang, "figures")
            data_files.append((path_xml, (glob.glob("%s/*.xml" % filepath))))
            data_files.append((path_figures,
                               (glob.glob("%s/figures/*.png" % filepath))))
        data_files.append((os.path.join('share/omf',
                                         self.distribution.metadata.name),
                           glob.glob("help/*/*.omf")))
