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

import os, sys, unittest, tempfile, shutil, platform

import hotwire
from hotwire.fs import path_join
from hotwire.completion import *
from hotwire.sysdep import is_windows, is_unix

class CompletionTests(unittest.TestCase):
    def setUp(self):
        self._tmpd = None
        self.vc = VerbCompleter()
        self.tc = TokenCompleter()
        self.pc = PathCompleter()  
        self.cc = CompletionSystem()      

    def tearDown(self):
        if self._tmpd:
            shutil.rmtree(self._tmpd)

    def _setupTree1(self):
        self._tmpd = tempfile.mkdtemp(prefix='hotwiretest')
        os.mkdir(path_join(self._tmpd, 'testdir'))
        if is_unix():
            self._test_exe = 'testf'
        elif is_windows():
            self._test_exe = 'testf.exe'
        self._test_exe_path = path_join(self._tmpd, self._test_exe)
        open(self._test_exe_path, 'w').close()
        if is_unix():
            os.chmod(self._test_exe_path, 744)            
        os.mkdir(path_join(self._tmpd, 'dir with spaces'))

    def _setupTree2(self):
        self._setupTree1()
        if is_unix(): 
            self._test_exe2_path = path_join(self._tmpd, 'testf2')
            open(self._test_exe2_path, 'w').close()
            os.chmod(self._test_exe2_path, 744)
        elif is_windows():
            self._test_exe2_path = path_join(self._tmpd, 'testf2.exe')
            open(self._test_exe2_path, 'w').close()
        open(path_join(self._tmpd, 'f3test'), 'w').close()
        open(path_join(self._tmpd, 'otherfile'), 'w').close()
        os.mkdir(path_join(self._tmpd, 'testdir2'))
        open(path_join(self._tmpd, 'testdir2', 'blah'), 'w').close()
        open(path_join(self._tmpd, 'testdir2', 'moo'), 'w').close()
        os.mkdir(path_join(self._tmpd, 'testdir2', 'moodir'))    

    def testCmdOrShell(self):
        if is_windows():
            search='cmd'
        else:
            search='true'
            verbs = list(self.vc.completions(search, "."))
            self.assertNotEqual(len(verbs), 0)

    def testNoCompletion(self):
        if is_windows():
            search='cmd'
        else:
            search='true'
            verbs = list(self.vc.completions('this does not exist', "."))
            self.assertEquals(len(verbs), 0)

    def testCwd(self):
        self._setupTree1()
        result = self.cc.sync_complete(self.pc, 'testf', self._tmpd)
        self.assertEquals(len(result.results), 1)
        self.assertEquals(result.results[0].target.path, self._test_exe_path)

    def testCwd2(self):
        self._setupTree1()
        result = self.cc.sync_complete(self.pc, 'no such thing', self._tmpd)
        self.assertEquals(len(result.results), 0)

    def testCwd3(self):
        self._setupTree1()
        result = self.cc.sync_complete(self.pc, 'test', self._tmpd)
        self.assertEquals(len(result.results), 2)
        self.assertEquals(result.results[0].target.path, path_join(self._tmpd, 'testdir'))
        self.assertEquals(result.results[1].target.path, self._test_exe_path)

    def testCwd4(self):
        self._setupTree2()
        result = self.cc.sync_complete(self.pc, 'testdir2/', self._tmpd)
        self.assertEquals(len(result.results), 3)
        self.assertEquals(result.results[0].target.path, path_join(self._tmpd, 'testdir2', 'blah'))        
        self.assertEquals(result.results[0].suffix, 'blah')
        self.assertEquals(result.results[1].suffix, 'moo')
        self.assertEquals(result.results[2].suffix, 'moodir/')

    def testCwd5(self):
        self._setupTree2()
        result = self.cc.sync_complete(self.pc, 'testdir2/m', self._tmpd)
        self.assertEquals(len(result.results), 2)
        self.assertEquals(result.results[0].target.path, path_join(self._tmpd, 'testdir2', 'moo'))           
        self.assertEquals(result.results[0].suffix, 'oo')
        self.assertEquals(result.results[1].suffix, 'oodir/')
        
    def testCwd6(self):
        self._setupTree1()
        result = self.cc.sync_complete(self.pc, './testd', self._tmpd)
        self.assertEquals(len(result.results), 1)
        self.assertEquals(result.common_prefix, None)        
        self.assertEquals(result.results[0].target.path, path_join(self._tmpd, '.', 'testdir'))
        self.assertEquals(result.results[0].suffix, 'ir/')

    def testCwd7(self):
        self._setupTree2()
        result = self.cc.sync_complete(self.pc, './f3', self._tmpd)
        self.assertEquals(len(result.results), 1)
        self.assertEquals(result.common_prefix, None) 
        self.assertEquals(result.results[0].target.path, path_join(self._tmpd, '.', 'f3test'))
        self.assertEquals(result.results[0].suffix, 'test')

    def testCwd8(self):
        self._setupTree1()
        result = self.cc.sync_complete(self.vc, './test', self._tmpd)
        self.assertEquals(len(result.results), 2)
        self.assertEquals(result.common_prefix, None)      
        self.assertEquals(result.results[0].target.path, path_join(self._tmpd, '.', 'testdir'))
        self.assertEquals(result.results[0].suffix, 'dir/')
        self.assertEquals(result.results[1].target.path, path_join(self._tmpd, '.', self._test_exe))
        self.assertEquals(result.results[1].suffix, self._test_exe[4:])
        
    def testCwd9(self):
        self._setupTree1()
        dotpath = path_join(self._tmpd, '.foo')
        f=open(dotpath, 'w')
        f.write('hi')
        f.close()
        dotpath = path_join(self._tmpd, '.bar')
        f=open(dotpath, 'w')
        f.write('there')
        f.close()                
        result = self.cc.sync_complete(self.pc, '', self._tmpd)
        self.assertEquals(len(result.results), 5)
        self.assertEquals(result.common_prefix, None)
        self.assertEquals(result.results[0].target.path, path_join(self._tmpd, '.bar'))
        self.assertEquals(result.results[0].suffix, '.bar')
        foo_index=2
        if is_windows():
            foo_index = 1
        self.assertEquals(result.results[foo_index].target.path, path_join(self._tmpd, '.foo'))
        self.assertEquals(result.results[foo_index].suffix, '.foo')
        
    def testSafechar1(self):
        self._setupTree1()
        bpath = path_join(self._tmpd, 'bar_foo')
        f=open(bpath, 'w')
        f.write('hi')
        f.close()              
        result = self.cc.sync_complete(self.pc, 'ba', self._tmpd)
        self.assertEquals(len(result.results), 1)
        self.assertEquals(result.common_prefix, None)
        self.assertEquals(result.results[0].target.path, bpath)
        self.assertEquals(result.results[0].suffix, 'r_foo')
        
    def testSafechar2(self):
        self._setupTree1()
        bpath = path_join(self._tmpd, 'bar+')
        os.mkdir(bpath)    
        result = self.cc.sync_complete(self.pc, 'ba', self._tmpd)
        self.assertEquals(len(result.results), 1)
        self.assertEquals(result.common_prefix, None)
        self.assertEquals(result.results[0].target.path, bpath)
        self.assertEquals(result.results[0].suffix, 'r+/')
        
    def testSpaces1(self):
        self._setupTree1()
        dpath = path_join(self._tmpd, 'dir with spaces')   
        result = self.cc.sync_complete(self.pc, 'di', self._tmpd)
        self.assertEquals(len(result.results), 1)
        self.assertEquals(result.common_prefix, None)
        self.assertEquals(result.results[0].target.path, dpath)
        self.assertEquals(result.results[0].suffix, r'r\ with\ spaces/')        

