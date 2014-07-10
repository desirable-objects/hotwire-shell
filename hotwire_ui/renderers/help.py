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

import StringIO

import gtk,gobject

from hotwire_ui.render import ClassRendererMapping
from hotwire_ui.renderers.unicode import UnicodeRenderer
from hotwire.cmdalias import AliasRegistry
from hotwire.command import PipelineLanguageRegistry
from hotwire.builtin import BuiltinRegistry, MultiArgSpec, ArgSpec
from hotwire.builtins.help import HelpItem
from hotwire_ui.pixbufcache import PixbufCache
from hotwire_ui.oinspect import InspectWindow 
from hotwire.version import __version__

class HelpItemRenderer(UnicodeRenderer):
    def __init__(self, context, **kwargs):
        super(HelpItemRenderer, self).__init__(context, monospace=False, **kwargs)
        self._buf.set_property('text', '')
        
    def append_inspectlink(self, text, o):
        def handle_inspector(text2):
            from hotwire_ui.shell import locate_current_window            
            inspect = InspectWindow(o, parent=locate_current_window(self.get_widget()))
            inspect.show_all()     
        self.append_link(text, handle_inspector)
        
    def __help_all(self):
        pbcache = PixbufCache.getInstance()        
        self._buf.insert_markup('Hotwire <i>%s</i>\n\n' % (__version__,))
        self._buf.insert_markup(_('Documentation on the web: '))
        self._buf.insert_markup(' ')
        self.append_link(_('Tutorial'), 'http://code.google.com/p/hotwire-shell/wiki/GettingStarted0700')
        self._buf.insert_markup(' ')
        external_pixbuf = pbcache.get('external.png', size=10)
        self._buf.insert_pixbuf(self._buf.get_end_iter(), external_pixbuf)         
        self._buf.insert_markup('\n\n')

        registry = BuiltinRegistry.getInstance()
        for (setname,builtins) in zip((_('User'), _('Standard'), _('System')), map(list, [registry.user_set, registry.hotwire_set, registry.system_set])):
            if len(builtins) == 0:
                continue 
            self._buf.insert_markup('<larger>%s:</larger>\n' % (_('%s Builtin Commands' % (setname,)),))
            builtins.sort(lambda a,b: cmp(a.name, b.name))
            for builtin in builtins:
                self.__append_builtin_base_help(builtin)
                self.__append_builtin_aliases(builtin)
                self.__append_builtin_arghelp(builtin)            
                self.__append_builtin_doc(builtin)
            self._buf.insert_markup('\n')

        self._buf.insert_markup('<larger>%s:</larger>\n' % (_('Languages'),))
        langreg = PipelineLanguageRegistry.getInstance()
        hotwire_lang = langreg['62270c40-a94a-44dd-aaa0-689f882acf34']
        python_lang = langreg['da3343a0-8bce-46ed-a463-2d17ab09d9b4']
        self.__append_language(hotwire_lang)
        self.__append_language(python_lang) 
        languages = list(langreg)       
        languages.sort(lambda a,b: cmp(a.langname, b.langname))
        for language in languages:
            if language in [hotwire_lang, python_lang]:
                continue
            self.__append_language(language)           
            
        self._buf.insert_markup('\n<larger>%s:</larger>\n' % (_('Aliases'),))
        aliases = list(AliasRegistry.getInstance())
        aliases.sort(lambda a,b: cmp(a.name,b.name))
        for alias in aliases:
            self._buf.insert_markup('  <b>%s</b> - %s\n' % tuple(map(gobject.markup_escape_text, (alias.name, alias.target))))
            
    def __append_language(self, language):
        pbcache = PixbufCache.getInstance()         
        self._buf.insert_markup(' ')
        if language.icon:
            lang_pixbuf = pbcache.get(language.icon, size=16, trystock=True, stocksize=gtk.ICON_SIZE_MENU)               
            self._buf.insert_pixbuf(self._buf.get_end_iter(), lang_pixbuf)
        else:
            self._buf.insert_markup(' ')            
        self.append_inspectlink(language.langname, language)
        if language.prefix is not None:
            self._buf.insert_markup(' - prefix: <tt>%s</tt>' \
                                % (gobject.markup_escape_text(language.prefix),))    
        self._buf.insert_markup('\n')

    def __append_builtin_base_help(self, builtin):
        self._buf.insert_markup(' ')
        pbcache = PixbufCache.getInstance()
        hotwire_pixbuf = pbcache.get('hotwire', size=16, trystock=True, stocksize=gtk.ICON_SIZE_MENU)               
        self._buf.insert_pixbuf(self._buf.get_end_iter(), hotwire_pixbuf)
        self.append_inspectlink(builtin.name, builtin)        
        self._buf.insert_markup(' - %s%s ' \
                                % (_('in'),
                                   builtin.input_is_optional and ' (opt):' or ':'))
        def append_type(t):
            if isinstance(t, type):
                self.append_inspectlink(str(t), t)
            else:
                self._buf.insert_markup(str(t))
        itype = builtin.input_type
        append_type(itype)
        self._buf.insert_markup('  %s: ' % (_('out'),))
        otype = builtin.output_type
        append_type(otype)
        self._buf.insert_markup('\n')
        
    def __append_builtin_aliases(self, builtin):
        if not builtin.aliases:
            return
        self._buf.insert_markup('    Aliases: ')
        names = ['<b>%s</b>' % (gobject.markup_escape_text(x),) for x in builtin.aliases]
        self._buf.insert_markup(', '.join(names))
        self._buf.insert_markup('\n')

    def __append_builtin_doc(self, builtin):
        if builtin.doc:
            for line in StringIO.StringIO(builtin.doc):
                self._buf.insert_markup('    ' + gobject.markup_escape_text(line))
            self._buf.insert_markup('\n')        
                
    def __append_builtin_arghelp(self, builtin):
        if builtin.argspec is None:
            self._buf.insert_markup('    <i>%s</i>\n' % (_('(No arguments)'),))                        
        elif builtin.argspec is not False:
            self._buf.insert_markup('    %s: ' % (_('Arguments'),))             
            if isinstance(builtin.argspec, tuple):
                for arg in builtin.argspec:
                    argname = gobject.markup_escape_text(arg.name)
                    if arg.opt:
                        argname = '[%s]' % (argname,)
                    self._buf.insert_markup('%s ' % (argname,))
            elif isinstance(builtin.argspec, MultiArgSpec):
                argname = gobject.markup_escape_text(builtin.argspec.name) + '*'
                self._buf.insert_markup(argname)
            else:
                assert False 
            self._buf.insert_markup('\n')
        else:
            assert builtin.argspec is False
            self._buf.insert_markup('    <i>%s</i>\n' % (_('(Unspecified arguments)'),))
        if not builtin.options:
            self._buf.insert_markup('    <i>%s</i>\n' % (_('(No options)'),))
        else:
            argstr = '  '.join(map(lambda x: ','.join(x), builtin.options))
            self._buf.insert_markup('    %s: ' % (_('Options'),))
            self._buf.insert_markup('<tt>' + gobject.markup_escape_text(argstr) + '</tt>')
            self._buf.insert_markup('\n')                
        
    def __help_items(self, items):   
        for builtin in items:
            self.__append_builtin_base_help(builtin)
            self.__append_builtin_aliases(builtin)
            self.__append_builtin_arghelp(builtin)
            self.__append_builtin_doc(builtin)

    def get_status_str(self):
        return ''

    def append_obj(self, o):
        if len(o.items) == 0:
            self.__help_all()
        else:
            self.__help_items(o.items)

    def get_autoscroll(self):
        return False
    
    def supports_input(self):
        return False

ClassRendererMapping.getInstance().register(HelpItem, HelpItemRenderer)
