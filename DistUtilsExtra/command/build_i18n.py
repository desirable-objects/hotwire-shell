"""distutils_extra.command.build_i18n

Implements the Distutils 'build_i18n' command."""

import distutils
import glob
import os
import os.path
import re
import sys
import distutils.command.build

class build_i18n(distutils.cmd.Command):

    description = "integrate the gettext framework"

    user_options = [('desktop-files=', None, '.desktop.in files that '
                                             'should be merged'),
                    ('xml-files=', None, '.xml.in files that should be '
                                         'merged'),
                    ('schemas-files=', None, '.schemas.in files that '
                                             'should be merged'),
                    ('ba-files=', None, 'bonobo-activation files that '
                                        'should be merged'),
                    ('rfc822deb-files=', None, 'RFC822 files that should '
                                               'be merged'),
                    ('key-files=', None, '.key.in files that should be '
                                         'merged'),
                    ('domain=', 'd', 'gettext domain'),
                    ('po-dir=', 'p', 'directory that holds the i18n files'),
                    ('bug-contact=', None, 'contact address for msgid bugs')]

    def initialize_options(self):
        self.desktop_files = []
        self.xml_files = []
        self.key_files = []
        self.schemas_files = []
        self.ba_files = []
        self.rfc822deb_files = []
        self.domain = None
        self.bug_contact = None
        self.po_dir = None

    def finalize_options(self):
        if self.domain is None:
            self.domain = self.distribution.metadata.name
        if self.po_dir is None:
            self.po_dir = "po"

    def run(self):
        """
        Update the language files, generate mo files and add them
        to the to be installed files
        """
        data_files = self.distribution.data_files

        if self.bug_contact is not None:
            os.environ["XGETTEXT_ARGS"] = "--msgid-bugs-address=%s " % \
                                          self.bug_contact

        # Print a warning if there is a Makefile that would overwrite our
        # values
        if os.path.exists("%s/Makefile" % self.po_dir):
            self.announce("""
WARNING: Intltool will use the values specified from the
         existing po/Makefile in favor of the vaules
         from setup.cfg.
         Remove the Makefile to avoid problems.""")

        # Update po(t) files and print a report
        # We have to change the working dir to the po dir for intltool
        cmd = ["intltool-update", "-r", "-g", self.domain]
        wd = os.getcwd()
        os.chdir(self.po_dir)
        self.spawn(cmd)
        os.chdir(wd)

        for po_file in glob.glob("%s/*.po" % self.po_dir):
            lang = os.path.basename(po_file[:-3])
            mo_dir =  os.path.join("build", "mo", lang, "LC_MESSAGES")
            mo_file = os.path.join(mo_dir, "%s.mo" % self.domain)
            if not os.path.exists(mo_dir):
                os.makedirs(mo_dir)
            cmd = ["msgfmt", po_file, "-o", mo_file]
            self.spawn(cmd)

            targetpath = os.path.join("share/locale", lang, "LC_MESSAGES")
            data_files.append((targetpath, (mo_file,)))

        # merge .in with translation
        for (option, switch) in ((self.xml_files, "-x"),
                                 (self.desktop_files, "-d"),
                                 (self.schemas_files, "-s"),
                                 (self.rfc822deb_files, "-r"),
                                 (self.ba_files, "-b"),
                                 (self.key_files, "-k"),):
            try:
                file_set = eval(option)
            except:
                continue
            for (target, files) in file_set:
                build_target = os.path.join("build", target)
                if not os.path.exists(build_target): 
                    os.makedirs(build_target)
                files_merged = []
                for file in files:
                    if file.endswith(".in"):
                        file_merged = os.path.basename(file[:-3])
                    else:
                        file_merged = os.path.basename(file)
                    file_merged = os.path.join(build_target, file_merged)
                    cmd = ["intltool-merge", switch, self.po_dir, file, 
                           file_merged]
                    self.spawn(cmd)
                    files_merged.append(file_merged)
                data_files.append((target, files_merged))

# class build
